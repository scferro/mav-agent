"""
TensorRT-LLM Model Interface for MAVLink Agent
Handles communication with TensorRT-LLM optimized models
"""

from typing import Dict, Any, Optional, List, Iterator, AsyncIterator, Sequence, Union, Callable
import json
import logging
import os
import traceback
import uuid
from pathlib import Path

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    BaseMessage,
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.callbacks.manager import CallbackManagerForLLMRun, AsyncCallbackManagerForLLMRun
from langchain_core.runnables import Runnable
from langchain_core.language_models import LanguageModelInput
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool

from config import get_model_settings

logger = logging.getLogger(__name__)
try:
    from tensorrt_llm import SamplingParams
    from tensorrt_llm.runtime import PYTHON_BINDINGS
    if PYTHON_BINDINGS:
        from tensorrt_llm.runtime import ModelRunnerCpp as ModelRunner
    else:
        from tensorrt_llm.runtime import ModelRunner
    TENSORRT_AVAILABLE = True
    TENSORRT_IMPORT_ERROR = None
    TENSORRT_IMPORT_TRACEBACK = None
except (ImportError, OSError, Exception) as import_error:
    # Capture the exact reason TensorRT-LLM could not be imported so we can
    # surface it to the caller instead of masking it behind a generic message.
    TENSORRT_AVAILABLE = False
    TENSORRT_IMPORT_ERROR = import_error
    TENSORRT_IMPORT_TRACEBACK = traceback.format_exc()
    logger.error("TensorRT-LLM import failed: %s", import_error)
    ModelRunner = None
    SamplingParams = None

class TensorRTInterface(BaseChatModel):
    """Interface for TensorRT-LLM optimized model communication"""
    
    def __init__(self, model_name: Optional[str] = None, model_path: Optional[str] = None):
        super().__init__()

        if not TENSORRT_AVAILABLE:
            error_message_lines = [
                "TensorRT-LLM is not available. Please install it with:",
                "pip install tensorrt_llm",
                "Note: Requires CUDA 12.x and compatible NVIDIA GPU."
            ]

            if TENSORRT_IMPORT_ERROR is not None:
                detailed_reason = (
                    f"Import error: {TENSORRT_IMPORT_ERROR.__class__.__name__}: "
                    f"{TENSORRT_IMPORT_ERROR}"
                )
                error_message_lines.append(detailed_reason)

            if TENSORRT_IMPORT_TRACEBACK is not None:
                error_message_lines.append(
                    "Full traceback saved in TENSORRT_IMPORT_TRACEBACK for debugging."
                )

            raise ImportError("\n".join(error_message_lines))

        model_settings = get_model_settings()
        
        # BaseChatModel inherits from Pydantic's BaseModel which prevents setting
        # new attributes via normal assignment. Use object.__setattr__ so these
        # configuration values are stored without tripping validation.
        object.__setattr__(self, 'model_name', model_name or model_settings['name'])
        object.__setattr__(self, 'model_path', model_path or model_settings.get('model_path', ''))
        object.__setattr__(self, 'tokenizer_path', model_settings.get('tokenizer_path'))
        object.__setattr__(self, 'temperature', model_settings['temperature'])
        object.__setattr__(self, 'top_p', model_settings['top_p'])
        object.__setattr__(self, 'top_k', model_settings['top_k'])
        object.__setattr__(self, 'max_tokens', model_settings['max_tokens'])
        
        self._llm = None
        self._sampling_params = None
        self._eos_token_id: Optional[int] = None
        self._pad_token_id: Optional[int] = None
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize the TensorRT LLM instance"""
        try:
            # Validate model path
            if not self.model_path:
                raise ValueError("model_path is required for TensorRT models")
            
            model_path = Path(self.model_path)
            if not model_path.exists():
                raise FileNotFoundError(f"TensorRT model not found at: {self.model_path}")
            
            # TensorRT-LLM defaults to spawning proxy worker processes via MPI + ZeroMQ.
            # On some setups this fails with "Socket operation on non-socket".
            # Falling back to the single-process worker avoids the flaky IPC layer.
            single_process_flag = os.environ.get("TLLM_WORKER_USE_SINGLE_PROCESS")
            if single_process_flag != "1":
                if single_process_flag is not None:
                    logger.warning(
                        "Overriding TLLM_WORKER_USE_SINGLE_PROCESS=%s to avoid TensorRT IPC issues.",
                        single_process_flag,
                    )
                os.environ["TLLM_WORKER_USE_SINGLE_PROCESS"] = "1"

            # Initialize TensorRT ModelRunner for pre-built engine
            # Use tokenizer_path from config or resolve from model path
            tokenizer_path = self.tokenizer_path
            if not tokenizer_path:
                tokenizer_path = self._resolve_tokenizer_path(model_path)

            if not tokenizer_path:
                raise ValueError(f"Could not find tokenizer for model at {model_path}")

            # Use ModelRunner.from_dir for pre-built TensorRT engines
            self._llm = ModelRunner.from_dir(
                engine_dir=str(model_path),
                rank=0,
                kv_cache_free_gpu_memory_fraction=0.25,  # Balance memory usage (~4-5GB) with context length (~8K tokens)
            )

            # Load tokenizer separately
            from transformers import AutoTokenizer
            self._tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_path), trust_remote_code=True)
            self._set_special_token_ids(self._tokenizer, tokenizer_path)

            # Store engine's max sequence length for dynamic token calculation
            self._engine_max_seq_len = self._llm.max_seq_len

            # Configure sampling parameters
            sampling_kwargs: Dict[str, Any] = {
                'temperature': self.temperature,
                'top_p': self.top_p,
                'top_k': self.top_k,
                'max_tokens': self.max_tokens or 32768,
            }
            if self._eos_token_id is not None:
                sampling_kwargs['end_id'] = self._eos_token_id
            if self._pad_token_id is not None:
                sampling_kwargs['pad_id'] = self._pad_token_id

            self._sampling_params = SamplingParams(**sampling_kwargs)
            
        except Exception as e:
            raise ConnectionError(f"Failed to initialize TensorRT model: {str(e)}")
    
    def _format_messages(
        self,
        messages: List[BaseMessage],
        tool_definitions: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Format messages using ChatML chat format (compatible with Qwen, Llama3, Mistral, and many other models)"""

        formatted_prompt = ""

        # Extract system message content if present
        system_content = None
        non_system_messages = []
        for message in messages:
            if isinstance(message, SystemMessage):
                system_content = message.content
            else:
                non_system_messages.append(message)

        # Combine system message and tools into single system block (matches Ollama)
        if system_content or tool_definitions:
            formatted_prompt += "<|im_start|>system\n"

            if system_content:
                formatted_prompt += system_content + "\n"

            if tool_definitions:
                formatted_prompt += "\n# Tools\n\n"
                formatted_prompt += "You may call one or more functions to assist with the user query.\n\n"
                formatted_prompt += "You are provided with function signatures within <tools></tools> XML tags:\n"
                formatted_prompt += "<tools>\n"
                for tool in tool_definitions:
                    # Match Ollama's format: {"type": "function", "function": {...}}
                    formatted_prompt += json.dumps({"type": "function", "function": tool.get("function", tool)}, ensure_ascii=False) + "\n"
                formatted_prompt += "</tools>\n\n"
                formatted_prompt += "For each function call, return a json object with function name and arguments within <tool_call></tool_call> XML tags:\n"
                formatted_prompt += "<tool_call>\n"
                formatted_prompt += '{"name": <function-name>, "arguments": <args-json-object>}\n'
                formatted_prompt += "</tool_call>\n"

            formatted_prompt += "<|im_end|>\n"

        # Process remaining messages
        for message in non_system_messages:
            if isinstance(message, HumanMessage):
                formatted_prompt += f"<|im_start|>user\n{message.content}<|im_end|>\n"
            elif isinstance(message, ToolMessage):
                # Tool responses use role "user" with <tool_response> wrapper (matches Ollama)
                tool_content = message.content
                if isinstance(tool_content, (dict, list)):
                    tool_content = json.dumps(tool_content, ensure_ascii=False)
                formatted_prompt += "<|im_start|>user\n"
                formatted_prompt += f"<tool_response>\n{tool_content}\n</tool_response>"
                formatted_prompt += "<|im_end|>\n"
            elif isinstance(message, AIMessage):
                formatted_prompt += "<|im_start|>assistant\n"

                # Check if this message has tool calls
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    # Format tool calls with XML wrapper (matches Ollama)
                    for tool_call in message.tool_calls:
                        tool_name = tool_call.get("name", "")
                        tool_args = tool_call.get("args", {})
                        if isinstance(tool_args, str):
                            try:
                                tool_args = json.loads(tool_args)
                            except:
                                pass
                        formatted_prompt += "<tool_call>\n"
                        formatted_prompt += json.dumps({"name": tool_name, "arguments": tool_args}, ensure_ascii=False) + "\n"
                        formatted_prompt += "</tool_call>\n"
                elif message.content:
                    # Regular text response
                    formatted_prompt += message.content

                formatted_prompt += "<|im_end|>\n"

        # Add assistant start token for generation
        formatted_prompt += "<|im_start|>assistant\n"

        return formatted_prompt

    def _resolve_tokenizer_path(self, engine_path: Path) -> Optional[Path]:
        configured = getattr(self, 'tokenizer_path', None)
        candidates: List[Optional[Path]] = []
        if configured:
            candidates.append(Path(configured))
        candidates.extend([
            engine_path,
            engine_path.parent,
            engine_path.parent.parent if engine_path.parent.parent != engine_path.parent else None,
        ])

        for candidate in candidates:
            if candidate is None:
                continue
            if not candidate.exists():
                continue
            if (candidate / "tokenizer.json").exists() or (candidate / "tokenizer_config.json").exists():
                return candidate
        return None

    def _set_special_token_ids(
        self,
        tokenizer: Optional[Any],
        tokenizer_path: Optional[Path],
    ) -> None:
        eos_id = getattr(tokenizer, "eos_token_id", None) if tokenizer is not None else None
        pad_id = getattr(tokenizer, "pad_token_id", None) if tokenizer is not None else None

        if pad_id is None and eos_id is not None:
            pad_id = eos_id

        if (eos_id is None or pad_id is None) and tokenizer_path is not None:
            eos_id, pad_id = self._load_special_token_ids_from_files(tokenizer_path, eos_id, pad_id)

        self._eos_token_id = eos_id
        self._pad_token_id = pad_id if pad_id is not None else eos_id

        if self._eos_token_id is None:
            logger.warning("Could not determine EOS token id for TensorRT model.")
        if self._pad_token_id is None:
            logger.warning("Could not determine PAD token id for TensorRT model.")

    def _load_special_token_ids_from_files(
        self,
        tokenizer_dir: Path,
        eos_id: Optional[int],
        pad_id: Optional[int],
    ) -> tuple[Optional[int], Optional[int]]:
        eos_token: Optional[str] = None
        pad_token: Optional[str] = None

        config_path = tokenizer_dir / "tokenizer_config.json"
        if config_path.exists():
            try:
                config_data = json.loads(config_path.read_text())
                eos_token = config_data.get("eos_token")
                pad_token = config_data.get("pad_token")
                added_tokens = config_data.get("added_tokens_decoder", {})

                def lookup(token_str: Optional[str]) -> Optional[int]:
                    if token_str is None:
                        return None
                    for token_id, meta in added_tokens.items():
                        if meta.get("content") == token_str:
                            return int(token_id)
                    return None

                eos_id = eos_id or lookup(eos_token)
                pad_id = pad_id or lookup(pad_token)
                if pad_token == eos_token and eos_id is not None:
                    pad_id = eos_id
            except Exception as exc:  # pragma: no cover - diagnostic warning only
                logger.warning("Failed to parse tokenizer_config.json: %s", exc)

        tokenizer_json_path = tokenizer_dir / "tokenizer.json"
        if (eos_id is None or pad_id is None) and tokenizer_json_path.exists():
            try:
                tokenizer_data = json.loads(tokenizer_json_path.read_text())
                vocab = tokenizer_data.get("model", {}).get("vocab", {})
                if eos_id is None and eos_token and eos_token in vocab:
                    eos_id = vocab[eos_token]
                if pad_id is None and pad_token and pad_token in vocab:
                    pad_id = vocab[pad_token]
            except Exception as exc:  # pragma: no cover - diagnostic warning only
                logger.warning("Failed to parse tokenizer.json: %s", exc)

        return eos_id, pad_id

    def _parse_tool_calls(
        self,
        response_text: str,
        tool_definitions: List[Dict[str, Any]],
        tool_choice: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """Parse tool calls from model response - handles both XML and JSON formats."""

        raw_text = response_text.strip()
        tool_calls = []

        # First try to extract <tool_call> XML blocks (matches Ollama format)
        import re
        tool_call_pattern = r'<tool_call>\s*(\{.*?\})\s*</tool_call>'
        xml_matches = re.findall(tool_call_pattern, raw_text, re.DOTALL)

        if xml_matches:
            # Parse each XML-wrapped JSON tool call
            for match in xml_matches:
                try:
                    parsed = json.loads(match)
                    if isinstance(parsed, dict) and "name" in parsed:
                        tool_calls.append(parsed)
                except json.JSONDecodeError:
                    continue
        else:
            # Fallback: try parsing as plain JSON (old format)
            parsed = None
            try:
                parsed = json.loads(raw_text)
            except json.JSONDecodeError:
                first = raw_text.find("{")
                last = raw_text.rfind("}")
                if first != -1 and last != -1 and last > first:
                    try:
                        parsed = json.loads(raw_text[first:last + 1])
                    except json.JSONDecodeError:
                        return []
                else:
                    return []

            if isinstance(parsed, dict) and "tool_calls" in parsed:
                tool_calls = parsed["tool_calls"]
            elif isinstance(parsed, list):
                tool_calls = parsed
            elif isinstance(parsed, dict) and {"name", "arguments"} <= parsed.keys():
                tool_calls = [parsed]
            else:
                return []

        valid_names = {
            tool.get("function", {}).get("name")
            for tool in tool_definitions
            if tool.get("type") == "function"
        }

        parsed_calls: List[Dict[str, Any]] = []
        for call in tool_calls:
            if not isinstance(call, dict):
                continue

            name = call.get("name") or call.get("function", {}).get("name")
            if not name or name not in valid_names:
                continue

            arguments = call.get("arguments") or call.get("function", {}).get("arguments", {})
            if isinstance(arguments, str):
                try:
                    arguments_payload = json.loads(arguments)
                except json.JSONDecodeError:
                    # If not valid JSON, wrap it in a dict
                    arguments_payload = {"raw": arguments}
            else:
                arguments_payload = arguments or {}

            # LangChain tool_call format expects 'name', 'args', 'id' keys
            # Don't include the nested 'function' key
            parsed_calls.append(
                {
                    "name": name,
                    "args": arguments_payload,
                    "id": call.get("id", str(uuid.uuid4())),
                }
            )

        if tool_choice and isinstance(tool_choice, dict):
            chosen_name = tool_choice.get("function", {}).get("name")
            if chosen_name:
                parsed_calls = [c for c in parsed_calls if c["name"] == chosen_name]

        return parsed_calls

    def _encode_prompt(self, prompt: str) -> Optional[List[int]]:
        if not hasattr(self, '_tokenizer') or self._tokenizer is None:
            return None
        try:
            tokens = self._tokenizer.encode(prompt, add_special_tokens=False)
            if isinstance(tokens, list):
                return tokens
            return None
        except Exception as exc:  # pragma: no cover - diagnostic warning only
            logger.warning("Failed to tokenize prompt for length calculation: %s", exc)
        return None
    
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate chat response using TensorRT-LLM"""
        try:
            # Extract tool metadata if present (bound via .bind_tools())
            tool_definitions = None
            tool_choice = None
            if "tools" in kwargs:
                tool_definitions = kwargs.pop("tools")
            if "tool_choice" in kwargs:
                tool_choice = kwargs.pop("tool_choice")

            # Format messages using ChatML format
            prompt = self._format_messages(messages, tool_definitions)

            # Tokenize prompt
            input_ids = self._tokenizer.encode(prompt, add_special_tokens=False)

            # Convert to torch tensor for TensorRT-LLM
            # TensorRT's ModelRunner expects tensors, not lists
            import torch
            if isinstance(input_ids, list):
                input_ids_tensor = torch.tensor(input_ids, dtype=torch.int32)
            elif hasattr(input_ids, 'to'):
                input_ids_tensor = input_ids.to(torch.int32)
            else:
                input_ids_tensor = torch.tensor(list(input_ids), dtype=torch.int32)

            # Calculate available output tokens: engine_limit - input_length
            input_len = len(input_ids)
            max_new_tokens = self._engine_max_seq_len - input_len

            # Generate using ModelRunner
            outputs = self._llm.generate(
                batch_input_ids=[input_ids_tensor],
                max_new_tokens=max_new_tokens,
                end_id=self._eos_token_id if self._eos_token_id else self._tokenizer.eos_token_id,
                pad_id=self._pad_token_id if self._pad_token_id else self._tokenizer.pad_token_id,
                temperature=kwargs.get('temperature', self.temperature),
                top_k=kwargs.get('top_k', self.top_k),
                top_p=kwargs.get('top_p', self.top_p),
                num_beams=1,
                return_dict=True,
            )

            # Decode output
            # outputs['output_ids'] is a torch tensor: [batch_size, beam_width, seq_len]
            import torch
            output_ids = outputs['output_ids'][0][0]  # Get first batch, first beam

            # Handle both tensor and list outputs
            if isinstance(output_ids, list):
                # Already a list, use as-is
                pass
            elif hasattr(output_ids, 'tolist'):
                output_ids = output_ids.tolist()
            else:
                output_ids = list(output_ids)

            # Remove input tokens from output
            # Use the tensor length for slicing
            input_len = len(input_ids) if isinstance(input_ids, list) else input_ids_tensor.shape[0]
            output_tokens = output_ids[input_len:]
            response_text = self._tokenizer.decode(output_tokens, skip_special_tokens=True).strip()

            tool_calls = []
            if tool_definitions and response_text:
                parsed_tool_calls = self._parse_tool_calls(response_text, tool_definitions, tool_choice)
                if parsed_tool_calls:
                    tool_calls = parsed_tool_calls
                    # When we interpret the response as a tool call, remove the JSON text content.
                    response_text = ""

            # Create chat generation
            generation = ChatGeneration(
                message=AIMessage(content=response_text, tool_calls=tool_calls),
                generation_info={
                    "finish_reason": "stop",
                    "model_name": self.model_name,
                    "prompt_tokens": input_len,
                    "completion_tokens": len(output_tokens),
                }
            )

            return ChatResult(generations=[generation])

        except Exception as e:
            raise RuntimeError(f"TensorRT generation failed: {str(e)}")
    
    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Async generate - falls back to sync for now"""
        # TensorRT-LLM doesn't have native async support yet
        return self._generate(messages, stop, run_manager, **kwargs)
    
    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGeneration]:
        """Stream chat response - not implemented yet for TensorRT-LLM"""
        # For now, return the full response as a single chunk
        result = self._generate(messages, stop, run_manager, **kwargs)
        yield result.generations[0]

    async def _astream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGeneration]:
        """Async stream chat response"""
        result = await self._agenerate(messages, stop, run_manager, **kwargs)
        yield result.generations[0]
    
    @property
    def _llm_type(self) -> str:
        """Return type of language model"""
        return "tensorrt_llm"

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        """Return identifying parameters"""
        return {
            "model_name": self.model_name,
            "model_path": self.model_path,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "max_tokens": self.max_tokens,
        }
    
    def is_available(self) -> bool:
        """Check if TensorRT model is available"""
        try:
            return TENSORRT_AVAILABLE and self._llm is not None and Path(self.model_path).exists()
        except Exception:
            return False
    
    def test_connection(self) -> tuple[bool, str]:
        """Test connection to TensorRT model"""
        if not TENSORRT_AVAILABLE:
            return False, "TensorRT-LLM not available. Please install tensorrt_llm package."
        
        if not self.model_path:
            return False, "Model path not configured"
        
        if not Path(self.model_path).exists():
            return False, f"Model not found at: {self.model_path}"
        
        if self._llm is None:
            return False, "Model not initialized"
        
        # Test simple generation
        try:
            test_messages = [HumanMessage(content="Test")]
            result = self._generate(test_messages)
            return True, "TensorRT model connection successful"
        except Exception as e:
            return False, f"Model test failed: {str(e)}"

    def bind_tools(
        self,
        tools: Sequence[Union[Dict[str, Any], type, Callable, BaseTool]],
        *,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, BaseMessage]:
        """Bind tool definitions to the model in OpenAI function-call format."""

        formatted_tools = [convert_to_openai_tool(tool) for tool in tools]
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice
        return super().bind(tools=formatted_tools, **kwargs)
