"""
Long-Term Memory Hook Provider for Strands Agents

Uses AgentCore Memory directly via hooks instead of the buggy SessionManager.
Based on: https://dev.to/aws-heroes/amazon-bedrock-agentcore-runtime-part-7-using-agentcore-long-term-memory-with-strands-agents-sdk-lb2
"""
import logging
from typing import Dict

from strands.hooks import HookProvider, HookRegistry
from strands.hooks.events import MessageAddedEvent, AfterInvocationEvent
from bedrock_agentcore.memory import MemoryClient

logger = logging.getLogger(__name__)


class LongTermMemoryHookProvider(HookProvider):
    """
    Hook provider that integrates AgentCore long-term memory with Strands agents.

    Automatically:
    - Retrieves relevant context before processing user messages
    - Saves conversation events after each invocation
    """

    def __init__(
        self,
        memory_client: MemoryClient,
        memory_id: str,
        actor_id: str,
        session_id: str,
        top_k: int = 50,
        relevance_score: float = 0.7
    ):
        """
        Initialize the memory hook provider.

        Args:
            memory_client: AgentCore MemoryClient instance
            memory_id: The memory ID from AgentCore
            actor_id: Actor identifier for memory operations
            session_id: Session identifier for memory operations
            top_k: Number of memories to retrieve per namespace
            relevance_score: Minimum relevance score for retrieved memories
        """
        self.memory_client = memory_client
        self.memory_id = memory_id
        self.actor_id = actor_id
        self.session_id = session_id
        self.top_k = top_k
        self.relevance_score = relevance_score
        self.namespaces = self._get_namespaces()

        logger.info(f"LongTermMemoryHookProvider initialized with memory_id={memory_id}, namespaces={list(self.namespaces.keys())}")

    def _get_namespaces(self) -> Dict[str, str]:
        """
        Retrieve available namespaces from memory strategies.

        Returns:
            Dict mapping strategy type to namespace pattern
        """
        try:
            strategies = self.memory_client.get_memory_strategies(self.memory_id)
            namespaces = {}
            for strategy in strategies:
                strategy_type = strategy.get("type", "unknown")
                namespace_list = strategy.get("namespaces", [])
                if namespace_list:
                    namespaces[strategy_type] = namespace_list[0]
            logger.info(f"Retrieved namespaces: {namespaces}")
            return namespaces
        except Exception as e:
            logger.warning(f"Failed to get memory strategies: {e}")
            # Fallback to expected namespaces based on CDK configuration
            return {
                "semantic": "/newsletter/articles/{actorId}",
                "user_preference": "/newsletter/preferences/{actorId}/{sessionId}"
            }

    def register_hooks(self, registry: HookRegistry) -> None:
        """Register memory hooks for context retrieval and event saving."""
        registry.add_callback(MessageAddedEvent, self._retrieve_context)
        registry.add_callback(AfterInvocationEvent, self._save_event)
        logger.info("Memory hooks registered")

    def _format_namespace(self, namespace_pattern: str) -> str:
        """Format namespace pattern with actor and session IDs."""
        return namespace_pattern.format(
            actorId=self.actor_id,
            sessionId=self.session_id
        )

    def _retrieve_context(self, event: MessageAddedEvent) -> None:
        """
        Retrieve relevant context from memory and enrich user query.

        Called automatically when a new message is added to the conversation.
        """
        try:
            messages = event.agent.messages

            # Only process user messages
            if not messages or messages[-1].get("role") != "user":
                return

            # Get the user's query
            content = messages[-1].get("content", [])
            if not content or not isinstance(content, list):
                return

            user_query = None
            for block in content:
                if isinstance(block, dict):
                    # Skip toolResult blocks - only process actual user text
                    if "toolResult" in block:
                        return  # This is a tool result, not a user query
                    if "text" in block:
                        user_query = block.get("text", "")
                        break
                elif isinstance(block, str):
                    user_query = block
                    break

            if not user_query:
                return

            logger.info(f"Retrieving memory context for query: {user_query[:100]}...")

            # Retrieve memories from all namespaces
            all_context = []

            for context_type, namespace_pattern in self.namespaces.items():
                try:
                    formatted_namespace = self._format_namespace(namespace_pattern)

                    memories = self.memory_client.retrieve_memories(
                        memory_id=self.memory_id,
                        namespace=formatted_namespace,
                        query=user_query,
                        top_k=self.top_k
                    )

                    for memory in memories:
                        if isinstance(memory, dict):
                            # Handle different memory response formats
                            text = ""
                            if "content" in memory:
                                content_obj = memory["content"]
                                if isinstance(content_obj, dict):
                                    text = content_obj.get("text", "")
                                elif isinstance(content_obj, str):
                                    text = content_obj
                            elif "text" in memory:
                                text = memory["text"]

                            text = text.strip()
                            if text:
                                all_context.append(f"[{context_type.upper()}] {text}")

                except Exception as e:
                    logger.warning(f"Failed to retrieve memories from {context_type}: {e}")
                    continue

            # Enrich the user query with context
            if all_context:
                context_text = "\n".join(all_context[:20])  # Limit context size

                # Update the message content with context
                for i, block in enumerate(messages[-1]["content"]):
                    if isinstance(block, dict) and "text" in block:
                        original_text = block["text"]
                        messages[-1]["content"][i]["text"] = (
                            f"=== MEMORY CONTEXT ===\n{context_text}\n=== END CONTEXT ===\n\n{original_text}"
                        )
                        logger.info(f"Enriched query with {len(all_context)} memory records")
                        break

        except Exception as e:
            logger.error(f"Error retrieving memory context: {e}", exc_info=True)

    def _save_event(self, event: AfterInvocationEvent) -> None:
        """
        Save the conversation event to memory.

        Called automatically after each agent invocation completes.
        """
        try:
            messages = event.agent.messages

            if not messages:
                logger.warning("No messages in agent for memory save")
                return

            # Debug: Log message structure
            logger.info(f"AfterInvocationEvent: {len(messages)} messages in conversation")
            for i, msg in enumerate(messages[-4:]):  # Last 4 messages
                role = msg.get("role", "unknown")
                content = msg.get("content", [])
                content_types = []
                for block in content if isinstance(content, list) else [content]:
                    if isinstance(block, dict):
                        content_types.append(block.get("type", "unknown"))
                    else:
                        content_types.append(type(block).__name__)
                logger.info(f"  Message {i}: role={role}, content_types={content_types}")

            # Extract the latest user query and final assistant response
            # Message structure in Strands:
            # - User message: [{"text": "..."}]
            # - Assistant with tools: [{"text": "..."}, {"toolUse": {...}}]
            # - Tool result (as user): [{"toolResult": {...}}]
            # - Final assistant: [{"text": "..."}]
            customer_query = None
            agent_response = None

            for msg in reversed(messages):
                role = msg.get("role")
                content = msg.get("content", [])

                if role == "assistant" and not agent_response:
                    # Extract text from assistant response - handle multiple text blocks
                    # Skip toolUse blocks, only get text
                    text_parts = []
                    for block in content if isinstance(content, list) else [content]:
                        if isinstance(block, dict) and "text" in block:
                            text_parts.append(block.get("text", ""))
                        elif isinstance(block, str):
                            text_parts.append(block)
                    if text_parts:
                        agent_response = " ".join(text_parts)

                elif role == "user" and not customer_query:
                    # Skip tool result messages (they have toolResult, not text)
                    # Only extract actual user queries
                    for block in content if isinstance(content, list) else [content]:
                        if isinstance(block, dict):
                            # Skip toolResult blocks - these are tool outputs, not user queries
                            if "toolResult" in block:
                                break  # This is a tool result message, skip it
                            if "text" in block:
                                text = block.get("text", "")
                                # Remove memory context if we added it
                                if "=== END CONTEXT ===" in text:
                                    text = text.split("=== END CONTEXT ===")[-1].strip()
                                customer_query = text
                                break
                        elif isinstance(block, str):
                            customer_query = block
                            break

                if customer_query and agent_response:
                    break

            if not customer_query or not agent_response:
                logger.warning(f"Could not extract query/response for memory save. query={customer_query is not None}, response={agent_response is not None}")
                return

            # Save to memory
            logger.info(f"Saving event to memory: query={customer_query[:50]}..., response={agent_response[:50]}...")

            self.memory_client.create_event(
                memory_id=self.memory_id,
                actor_id=self.actor_id,
                session_id=self.session_id,
                messages=[
                    (customer_query, "USER"),
                    (agent_response, "ASSISTANT")
                ]
            )

            logger.info("Successfully saved event to memory")

        except Exception as e:
            logger.error(f"Error saving event to memory: {e}", exc_info=True)
