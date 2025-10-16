from .agent import TellTimeAgent
from a2a.server.agent_execution import AgentExecutor
from a2a.server.agent_execution import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.types import (
    TaskArtifactUpdateEvent,
    TaskStatusUpdateEvent,
    TaskStatus,
    TaskState,
)
from a2a.utils import (
    new_agent_text_message,
    new_task,
    new_text_artifact
)

class TellTimeAgentExecutor(AgentExecutor):
    def __init__(self):
        self.agent = TellTimeAgent()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        query = context.get_user_input()
        task = context.current_task

        if not context.message:
            raise Exception('No message provided')

        if not task:
            task = new_task(context.message)
            event_queue.enqueue_event(task)

        async for event in self.agent.stream(query, task.contextId):
            if event['is_task_complete']:
                event_queue.enqueue_event(
                    TaskArtifactUpdateEvent(
                        taskId=task.id,
                        contextId=task.contextId,
                        artifact=new_text_artifact(
                            name='current_result',
                            description='Result of request to agent.',
                            text=event['content'],
                        ),
                        append=False,
                        lastChunk=True,
                    )
                )
                event_queue.enqueue_event(
                    TaskStatusUpdateEvent(
                        taskId=task.id,
                        contextId=task.contextId,
                        status=TaskStatus(state=TaskState.completed),
                        final=True,
                    )
                )
            elif event['require_user_input']:
                event_queue.enqueue_event(
                    TaskStatusUpdateEvent(
                        taskId=task.id,
                        contextId=task.contextId,
                        status=TaskStatus(
                            state=TaskState.input_required,
                            message=new_agent_text_message(
                                event['content'],
                                task.contextId,
                                task.id
                            ),
                        ),
                        final=True,
                    )
                )
            else:
                event_queue.enqueue_event(
                    TaskStatusUpdateEvent(
                        taskId=task.id,
                        contextId=task.contextId,
                        status=TaskStatus(
                            state=TaskState.working,
                            message=new_agent_text_message(
                                event['content'],
                                task.contextId,
                                task.id
                            ),
                        ),
                        final=False,
                    )
                )