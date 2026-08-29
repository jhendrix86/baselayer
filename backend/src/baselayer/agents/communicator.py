"""
BaseLayer Agent Communicator

Inter-agent communication protocols and message handling
for the Multi-Agent Orchestration subsystem.
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from structlog import get_logger

from ..core.database import db_session_context
from ..models.agents import (
    Agent, AgentMessage,
    AgentType, AgentStatus
)
from .exceptions import (
    AgentCommunicationError,
    AgentNotFoundError
)

logger = get_logger(__name__)


class MessageType(Enum):
    """Types of inter-agent messages."""
    TASK_REQUEST = "task_request"
    TASK_RESPONSE = "task_response"
    TASK_UPDATE = "task_update"
    HEARTBEAT = "heartbeat"
    STATUS_UPDATE = "status_update"
    RESOURCE_REQUEST = "resource_request"
    RESOURCE_RESPONSE = "resource_response"
    COORDINATION = "coordination"
    COLLABORATION = "collaboration"
    ERROR = "error"
    INFO = "info"


class MessagePriority(Enum):
    """Message priority levels."""
    CRITICAL = 100
    HIGH = 75
    MEDIUM = 50
    LOW = 25


class AgentCommunicator:
    """
    Inter-agent communication system.
    
    Handles message routing, protocol management, and
    communication monitoring between agents.
    """
    
    def __init__(self):
        self.communication_active: bool = False
        self.message_queues: Dict[str, asyncio.Queue] = {}
        self.message_handlers: Dict[MessageType, callable] = {}
        self.communication_protocols = {
            "direct": self._direct_protocol,
            "broadcast": self._broadcast_protocol,
            "multicast": self._multicast_protocol,
            "publish_subscribe": self._publish_subscribe_protocol
        }
        self.default_protocol = "direct"
        self.message_timeout: int = 30  # seconds
        self.max_message_size: int = 1024 * 1024  # 1MB
        self.message_history: Dict[str, List[AgentMessage]] = {}
        self.max_history_size: int = 1000
        
        # Communication metrics
        self.communication_metrics = {
            "messages_sent": 0,
            "messages_received": 0,
            "messages_failed": 0,
            "average_response_time": 0.0
        }
    
    async def start(self) -> None:
        """Start the communication system."""
        if self.communication_active:
            return
        
        self.communication_active = True
        self._register_default_handlers()
        asyncio.create_task(self._communication_loop())
        
        logger.info("Agent communicator started")
    
    async def stop(self) -> None:
        """Stop the communication system."""
        self.communication_active = False
        logger.info("Agent communicator stopped")
    
    async def send_message(
        self,
        target_agent_id: str,
        message_type: Union[str, MessageType],
        message_data: Dict[str, Any],
        priority: MessagePriority = MessagePriority.MEDIUM,
        protocol: Optional[str] = None,
        timeout: Optional[int] = None,
        correlation_id: Optional[str] = None,
        reply_to: Optional[str] = None
    ) -> AgentMessage:
        """
        Send a message to an agent.
        
        Args:
            target_agent_id: Target agent ID
            message_type: Type of message
            message_data: Message data
            priority: Message priority
            protocol: Communication protocol
            timeout: Message timeout
            correlation_id: Correlation ID for request/response
            reply_to: Message ID this is replying to
            
        Returns:
            AgentMessage: Created message
            
        Raises:
            AgentCommunicationError: If sending fails
        """
        try:
            # Validate target agent
            if not await self._validate_agent(target_agent_id):
                raise AgentNotFoundError(f"Target agent not found: {target_agent_id}")
            
            # Validate message
            await self._validate_message(message_type, message_data)
            
            # Create message
            message = AgentMessage(
                id=uuid.uuid4(),
                sender_id=None,  # Will be set by orchestrator
                recipient_id=uuid.UUID(target_agent_id),
                message_type=message_type.value if isinstance(message_type, MessageType) else message_type,
                message_data=message_data,
                priority=priority.value,
                protocol=protocol or self.default_protocol,
                timeout=timeout or self.message_timeout,
                correlation_id=correlation_id,
                reply_to=reply_to,
                status="sent",
                created_at=datetime.utcnow()
            )
            
            # Store message
            await self._store_message(message)
            
            # Send using protocol
            protocol_name = protocol or self.default_protocol
            if protocol_name not in self.communication_protocols:
                raise AgentCommunicationError(f"Unknown protocol: {protocol_name}")
            
            await self.communication_protocols[protocol_name](message)
            
            # Update metrics
            self.communication_metrics["messages_sent"] += 1
            
            logger.info(
                "Message sent",
                message_id=str(message.id),
                target_agent_id=target_agent_id,
                message_type=message.value if isinstance(message_type, MessageType) else message_type
            )
            
            return message
            
        except Exception as e:
            self.communication_metrics["messages_failed"] += 1
            raise AgentCommunicationError(f"Failed to send message: {str(e)}") from e
    
    async def broadcast_message(
        self,
        message_type: Union[str, MessageType],
        message_data: Dict[str, Any],
        priority: MessagePriority = MessagePriority.MEDIUM,
        agent_type: Optional[AgentType] = None,
        exclude_agents: Optional[List[str]] = None
    ) -> List[AgentMessage]:
        """
        Broadcast a message to multiple agents.
        
        Args:
            message_type: Type of message
            message_data: Message data
            priority: Message priority
            agent_type: Filter by agent type
            exclude_agents: Agents to exclude
            
        Returns:
            List[AgentMessage]: Sent messages
        """
        try:
            # Get target agents
            target_agents = await self._get_broadcast_targets(agent_type, exclude_agents)
            
            messages = []
            for agent_id in target_agents:
                try:
                    message = await self.send_message(
                        target_agent_id=agent_id,
                        message_type=message_type,
                        message_data=message_data,
                        priority=priority,
                        protocol="broadcast"
                    )
                    messages.append(message)
                except Exception as e:
                    logger.error(
                        "Failed to send broadcast message",
                        target_agent_id=agent_id,
                        error=str(e)
                    )
            
            logger.info(
                "Broadcast message sent",
                message_type=message.value if isinstance(message_type, MessageType) else message_type,
                target_count=len(messages)
            )
            
            return messages
            
        except Exception as e:
            raise AgentCommunicationError(f"Failed to broadcast message: {str(e)}") from e
    
    async def process_message(
        self,
        agent_id: str,
        message: AgentMessage
    ) -> None:
        """
        Process a received message.
        
        Args:
            agent_id: Agent ID that received the message
            message: Message to process
        """
        try:
            # Update message status
            message.status = "processing"
            message.processed_at = datetime.utcnow()
            await self._update_message(message)
            
            # Get message type
            try:
                msg_type = MessageType(message.message_type)
            except ValueError:
                msg_type = message.message_type
            
            # Handle message
            if msg_type in self.message_handlers:
                await self.message_handlers[msg_type](agent_id, message)
            else:
                await self._handle_unknown_message(agent_id, message)
            
            # Update status
            message.status = "processed"
            await self._update_message(message)
            
            # Update metrics
            self.communication_metrics["messages_received"] += 1
            
            logger.debug(
                "Message processed",
                message_id=str(message.id),
                agent_id=agent_id,
                message_type=message.message_type
            )
            
        except Exception as e:
            # Mark as failed
            message.status = "failed"
            message.error_message = str(e)
            await self._update_message(message)
            
            self.communication_metrics["messages_failed"] += 1
            
            logger.error(
                "Message processing failed",
                message_id=str(message.id),
                agent_id=agent_id,
                error=str(e)
            )
    
    async def get_message_history(
        self,
        agent_id: Optional[str] = None,
        message_type: Optional[Union[str, MessageType]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AgentMessage]:
        """
        Get message history.
        
        Args:
            agent_id: Filter by agent ID
            message_type: Filter by message type
            limit: Maximum number of results
            offset: Pagination offset
            
        Returns:
            List[AgentMessage]: Message history
        """
        try:
            async with db_session_context() as session:
                query = select(AgentMessage).where(AgentMessage.deleted_at.is_(None))
                
                if agent_id:
                    query = query.where(
                        (AgentMessage.sender_id == uuid.UUID(agent_id)) |
                        (AgentMessage.recipient_id == uuid.UUID(agent_id))
                    )
                
                if message_type:
                    msg_type = message_type.value if isinstance(message_type, MessageType) else message_type
                    query = query.where(AgentMessage.message_type == msg_type)
                
                query = query.order_by(AgentMessage.created_at.desc())
                query = query.limit(limit).offset(offset)
                
                result = await session.execute(query)
                messages = result.scalars().all()
                
                return list(messages)
                
        except Exception as e:
            raise AgentCommunicationError(f"Failed to get message history: {str(e)}") from e
    
    async def get_communication_stats(self) -> Dict[str, Any]:
        """
        Get communication statistics.
        
        Returns:
            Dict[str, Any]: Communication statistics
        """
        try:
            async with db_session_context() as session:
                # Get message counts by type
                result = await session.execute(
                    select(
                        AgentMessage.message_type,
                        func.count(AgentMessage.id)
                    ).where(
                        AgentMessage.deleted_at.is_(None)
                    ).group_by(AgentMessage.message_type)
                )
                message_counts = dict(result.all())
                
                # Get message counts by status
                result = await session.execute(
                    select(
                        AgentMessage.status,
                        func.count(AgentMessage.id)
                    ).where(
                        AgentMessage.deleted_at.is_(None)
                    ).group_by(AgentMessage.status)
                )
                status_counts = dict(result.all())
                
                # Get average response time
                result = await session.execute(
                    select(
                        func.avg(
                            func.extract('epoch', AgentMessage.processed_at) - 
                            func.extract('epoch', AgentMessage.created_at)
                        )
                    ).where(
                        AgentMessage.processed_at.is_not(None),
                        AgentMessage.deleted_at.is_(None)
                    )
                )
                
                avg_response_time = result.scalar()
                
                stats = {
                    "communication_active": self.communication_active,
                    "default_protocol": self.default_protocol,
                    "available_protocols": list(self.communication_protocols.keys()),
                    "message_queues": len(self.message_queues),
                    "message_history_size": sum(len(history) for history in self.message_history.values()),
                    "metrics": {
                        **self.communication_metrics,
                        "average_response_time": float(avg_response_time) if avg_response_time else 0.0,
                        "by_type": message_counts,
                        "by_status": status_counts
                    }
                }
                
                return stats
                
        except Exception as e:
            raise AgentCommunicationError(f"Failed to get communication stats: {str(e)}") from e
    
    async def _communication_loop(self) -> None:
        """Main communication processing loop."""
        while self.communication_active:
            try:
                # Process message queues
                for agent_id, queue in self.message_queues.items():
                    while not queue.empty():
                        try:
                            message = queue.get_nowait()
                            await self.process_message(agent_id, message)
                        except asyncio.QueueEmpty:
                            break
                
                # Sleep before next iteration
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(
                    "Communication loop error",
                    error=str(e)
                )
                await asyncio.sleep(1)
    
    async def _direct_protocol(self, message: AgentMessage) -> None:
        """Direct message protocol - send to specific agent."""
        recipient_id = str(message.recipient_id)
        
        if recipient_id not in self.message_queues:
            # Create queue for agent
            self.message_queues[recipient_id] = asyncio.Queue()
        
        # Add to agent's queue
        await self.message_queues[recipient_id].put(message)
    
    async def _broadcast_protocol(self, message: AgentMessage) -> None:
        """Broadcast protocol - send to all agents."""
        # Get all active agents
        async with db_session_context() as session:
            result = await session.execute(
                select(Agent).where(
                    Agent.status == AgentStatus.ACTIVE,
                    Agent.deleted_at.is_(None)
                )
            )
            agents = result.scalars().all()
            
        # Send to all agents
        for agent in agents:
            agent_id = str(agent.id)
            if agent_id not in self.message_queues:
                self.message_queues[agent_id] = asyncio.Queue()
            
            # Create copy of message for each agent
            broadcast_message = AgentMessage(
                id=uuid.uuid4(),
                sender_id=message.sender_id,
                recipient_id=agent.id,
                message_type=message.message_type,
                message_data=message.message_data,
                priority=message.priority,
                protocol="broadcast",
                timeout=message.timeout,
                correlation_id=message.correlation_id,
                reply_to=message.reply_to,
                status="sent",
                created_at=datetime.utcnow()
            )
            
            await self.message_queues[agent_id].put(broadcast_message)
    
    async def _multicast_protocol(self, message: AgentMessage) -> None:
        """Multicast protocol - send to multiple specific agents."""
        # This would be implemented based on message data specifying target agents
        # For now, fall back to direct protocol
        await self._direct_protocol(message)
    
    async def _publish_subscribe_protocol(self, message: AgentMessage) -> None:
        """Publish-subscribe protocol - topic-based messaging."""
        # This would be implemented with topic subscription management
        # For now, fall back to broadcast protocol
        await self._broadcast_protocol(message)
    
    async def _store_message(self, message: AgentMessage) -> None:
        """Store message in database."""
        async with db_session_context() as session:
            session.add(message)
            await session.commit()
            
            # Add to history
            recipient_id = str(message.recipient_id)
            if recipient_id not in self.message_history:
                self.message_history[recipient_id] = []
            
            self.message_history[recipient_id].append(message)
            
            # Limit history size
            if len(self.message_history[recipient_id]) > self.max_history_size:
                self.message_history[recipient_id] = self.message_history[recipient_id][-self.max_history_size:]
    
    async def _update_message(self, message: AgentMessage) -> None:
        """Update message in database."""
        async with db_session_context() as session:
            session.add(message)
            await session.commit()
    
    async def _validate_agent(self, agent_id: str) -> bool:
        """Validate that an agent exists and is active."""
        try:
            async with db_session_context() as session:
                result = await session.execute(
                    select(Agent).where(
                        Agent.id == uuid.UUID(agent_id),
                        Agent.status == AgentStatus.ACTIVE,
                        Agent.deleted_at.is_(None)
                    )
                )
                return result.scalar_one_or_none() is not None
        except Exception:
            return False
    
    async def _validate_message(self, message_type: Union[str, MessageType], message_data: Dict[str, Any]) -> None:
        """Validate message data."""
        # Check message size
        data_size = len(json.dumps(message_data))
        if data_size > self.max_message_size:
            raise AgentCommunicationError(f"Message too large: {data_size} bytes")
        
        # Validate message type
        if isinstance(message_type, MessageType):
            return  # Valid enum value
        
        # Check if it's a valid string
        if not isinstance(message_type, str):
            raise AgentCommunicationError("Message type must be string or MessageType enum")
    
    async def _get_broadcast_targets(
        self,
        agent_type: Optional[AgentType],
        exclude_agents: Optional[List[str]]
    ) -> List[str]:
        """Get target agents for broadcast."""
        try:
            async with db_session_context() as session:
                query = select(Agent).where(
                    Agent.status == AgentStatus.ACTIVE,
                    Agent.deleted_at.is_(None)
                )
                
                if agent_type:
                    query = query.where(Agent.agent_type == agent_type)
                
                if exclude_agents:
                    exclude_uuids = [uuid.UUID(agent_id) for agent_id in exclude_agents]
                    query = query.where(Agent.id.notin_(exclude_uuids))
                
                result = await session.execute(query)
                agents = result.scalars().all()
                
                return [str(agent.id) for agent in agents]
                
        except Exception as e:
            logger.error(
                "Failed to get broadcast targets",
                error=str(e)
            )
            return []
    
    def _register_default_handlers(self) -> None:
        """Register default message handlers."""
        self.message_handlers[MessageType.HEARTBEAT] = self._handle_heartbeat
        self.message_handlers[MessageType.STATUS_UPDATE] = self._handle_status_update
        self.message_handlers[MessageType.TASK_RESPONSE] = self._handle_task_response
        self.message_handlers[MessageType.ERROR] = self._handle_error_message
        self.message_handlers[MessageType.RESOURCE_REQUEST] = self._handle_resource_request
        self.message_handlers[MessageType.RESOURCE_RESPONSE] = self._handle_resource_response
    
    async def _handle_heartbeat(self, agent_id: str, message: AgentMessage) -> None:
        """Handle heartbeat message."""
        logger.debug(
            "Heartbeat received",
            agent_id=agent_id,
            message_id=str(message.id)
        )
        
        # Update agent last activity
        try:
            async with db_session_context() as session:
                result = await session.execute(
                    select(Agent).where(Agent.id == uuid.UUID(agent_id))
                )
                agent = result.scalar_one_or_none()
                
                if agent:
                    agent.last_activity = datetime.utcnow()
                    session.add(agent)
                    await session.commit()
                    
        except Exception as e:
            logger.error(
                "Failed to update agent heartbeat",
                agent_id=agent_id,
                error=str(e)
            )
    
    async def _handle_status_update(self, agent_id: str, message: AgentMessage) -> None:
        """Handle status update message."""
        status_data = message.message_data
        new_status = status_data.get("status")
        
        if new_status:
            try:
                async with db_session_context() as session:
                    result = await session.execute(
                        select(Agent).where(Agent.id == uuid.UUID(agent_id))
                    )
                    agent = result.scalar_one_or_none()
                    
                    if agent:
                        agent.status = AgentStatus(new_status)
                        agent.last_activity = datetime.utcnow()
                        session.add(agent)
                        await session.commit()
                        
                        logger.info(
                            "Agent status updated",
                            agent_id=agent_id,
                            new_status=new_status
                        )
                        
            except Exception as e:
                logger.error(
                    "Failed to update agent status",
                    agent_id=agent_id,
                    error=str(e)
                )
    
    async def _handle_task_response(self, agent_id: str, message: AgentMessage) -> None:
        """Handle task response message."""
        # This would be handled by the orchestrator
        logger.debug(
            "Task response received",
            agent_id=agent_id,
            message_id=str(message.id)
        )
    
    async def _handle_error_message(self, agent_id: str, message: AgentMessage) -> None:
        """Handle error message."""
        error_data = message.message_data
        error_message = error_data.get("error", "Unknown error")
        
        logger.error(
            "Agent error reported",
            agent_id=agent_id,
            message_id=str(message.id),
            error=error_message
        )
    
    async def _handle_resource_request(self, agent_id: str, message: AgentMessage) -> None:
        """Handle resource request message."""
        # This would be handled by the resource manager
        logger.debug(
            "Resource request received",
            agent_id=agent_id,
            message_id=str(message.id)
        )
    
    async def _handle_resource_response(self, agent_id: str, message: AgentMessage) -> None:
        """Handle resource response message."""
        # This would be handled by the resource manager
        logger.debug(
            "Resource response received",
            agent_id=agent_id,
            message_id=str(message.id)
        )
    
    async def _handle_unknown_message(self, agent_id: str, message: AgentMessage) -> None:
        """Handle unknown message type."""
        logger.warning(
            "Unknown message type received",
            agent_id=agent_id,
            message_id=str(message.id),
            message_type=message.message_type
        )
