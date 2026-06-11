import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import type {
  AdminTask,
  AdminTaskCreateRequest,
  AdminTaskEvent,
  AdminTaskPriorityEnum,
  AdminTaskStatusEnum,
  AdminTaskTypeEnum,
  PatchedAdminTaskUpdateRequest,
  V1AdminOpsTasksListParams
} from "../api/generated/banxumApi";
import {
  AdminTaskPriorityEnum as TaskPriority,
  AdminTaskStatusEnum as TaskStatus,
  AdminTaskTypeEnum as TaskType,
  useV1AdminOpsTasksCreate,
  useV1AdminOpsTasksPartialUpdate
} from "../api/generated/banxumApi";
import { isFixturePreview } from "../investorPortal/data";
import { formatDateTime } from "../investorPortal/format";
import {
  Banner,
  Button,
  Card,
  Chip,
  Empty,
  Field,
  Modal,
  type Tone
} from "../investorPortal/ui";
import { adminTaskEventsFixture, adminTasksFixture } from "./adminFixtures";
import { useAdminTaskEventsData, useAdminTasksData } from "./data";

const taskTypeOptions = Object.values(TaskType);
const taskStatusOptions = Object.values(TaskStatus);
const taskPriorityOptions = Object.values(TaskPriority);

type TaskFilters = {
  status: "" | AdminTaskStatusEnum;
  priority: "" | AdminTaskPriorityEnum;
  taskType: "" | AdminTaskTypeEnum;
  search: string;
};

function labelize(value: string | null | undefined) {
  if (!value) return "-";
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function priorityTone(priority: string): Tone {
  if (priority === "urgent") return "bad";
  if (priority === "high") return "warn";
  if (priority === "low") return "neutral";
  return "info";
}

function statusTone(status: string): Tone {
  if (status === "resolved") return "ok";
  if (status === "cancelled") return "neutral";
  if (status === "waiting") return "warn";
  if (status === "in_progress") return "info";
  return "accent";
}

function errorMessage(error: unknown) {
  if (error instanceof Error) return error.message;
  return "The task request failed. Try again or check the backend session.";
}

function refetchLive(refetch: () => Promise<unknown>) {
  if (!isFixturePreview) void refetch();
}

function dueLocalValue(value: string | null | undefined) {
  if (!value) return "";
  return value.slice(0, 16);
}

function localValueToIso(value: string) {
  return value ? new Date(value).toISOString() : null;
}

function isTerminalStatus(status: string) {
  return status === "resolved" || status === "cancelled";
}

function zurichBusinessDate() {
  return new Date().toLocaleDateString("en-CA", { timeZone: "Europe/Zurich" });
}

function taskMatchesSearch(task: AdminTask, search: string) {
  const normalized = search.trim().toLowerCase();
  if (!normalized) return true;
  return [
    task.title,
    task.notes,
    task.related_object_type,
    task.related_object_id,
    task.task_type,
    task.status,
    task.priority
  ].some((value) => value.toLowerCase().includes(normalized));
}

function eventForPreview(
  task: AdminTask,
  eventType: string,
  previousStatus: string,
  newStatus: string,
  note: string
): AdminTaskEvent {
  return {
    id: `preview-event-${task.id}-${Date.now()}`,
    task_id: task.id,
    event_type: eventType,
    actor_user_id: "preview-admin",
    actor_account_type: "admin",
    previous_status: previousStatus,
    new_status: newStatus,
    note,
    metadata: { preview: true },
    occurred_at: new Date().toISOString()
  };
}

export function AdminTasksPanel() {
  const [filters, setFilters] = useState<TaskFilters>({
    status: "",
    priority: "",
    taskType: "",
    search: ""
  });
  const [previewTasks, setPreviewTasks] = useState(adminTasksFixture);
  const [previewEvents, setPreviewEvents] = useState(adminTaskEventsFixture);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const params: V1AdminOpsTasksListParams = useMemo(() => {
    const next: V1AdminOpsTasksListParams = { limit: 100 };
    if (filters.status) next.status = filters.status;
    if (filters.priority) next.priority = filters.priority;
    if (filters.taskType) next.task_type = filters.taskType;
    return next;
  }, [filters.priority, filters.status, filters.taskType]);

  const tasksQuery = useAdminTasksData(params);
  const liveTasks = tasksQuery.data ?? [];
  const baseTasks = isFixturePreview ? previewTasks : liveTasks;
  const tasks = baseTasks.filter((task) => taskMatchesSearch(task, filters.search));
  const selectedTask = baseTasks.find((task) => task.id === selectedTaskId) ?? null;
  const eventsQuery = useAdminTaskEventsData(selectedTaskId);
  const selectedEvents = isFixturePreview
    ? selectedTaskId
      ? (previewEvents[selectedTaskId] ?? [])
      : []
    : (eventsQuery.data ?? []);
  const openCount = baseTasks.filter((task) => !task.is_terminal).length;
  const urgentCount = baseTasks.filter((task) => task.priority === "urgent" && !task.is_terminal).length;
  const today = zurichBusinessDate();
  const dueTodayCount = baseTasks.filter((task) => task.due_at?.slice(0, 10) === today && !task.is_terminal).length;

  function updatePreviewTask(taskId: string, changes: PatchedAdminTaskUpdateRequest) {
    setPreviewTasks((current) =>
      current.map((task) => {
        if (task.id !== taskId) return task;
        const previousStatus = task.status;
        const nextStatus = changes.status ?? task.status;
        const nextTask: AdminTask = {
          ...task,
          task_type: changes.task_type ?? task.task_type,
          title: changes.title ?? task.title,
          priority: changes.priority ?? task.priority,
          status: nextStatus,
          assigned_admin_id: changes.clear_assigned_admin ? null : changes.assigned_admin_id ?? task.assigned_admin_id,
          due_at: changes.clear_due_at ? null : changes.due_at ?? task.due_at,
          notes: changes.notes ?? task.notes,
          completion_note: changes.completion_note ?? task.completion_note,
          completed_at: isTerminalStatus(nextStatus) ? (task.completed_at ?? new Date().toISOString()) : null,
          is_terminal: isTerminalStatus(nextStatus),
          updated_at: new Date().toISOString()
        };
        setPreviewEvents((events) => ({
          ...events,
          [taskId]: [
            ...(events[taskId] ?? []),
            eventForPreview(
              nextTask,
              previousStatus === nextStatus ? "updated" : "status_changed",
              previousStatus,
              nextStatus,
              changes.completion_note || changes.notes || "Task updated in preview mode."
            )
          ]
        }));
        return nextTask;
      })
    );
  }

  function createPreviewTask(data: AdminTaskCreateRequest) {
    const task: AdminTask = {
      id: `preview-task-${Date.now()}`,
      task_type: data.task_type,
      title: data.title,
      priority: data.priority ?? "normal",
      status: "open",
      assigned_admin_id: data.assigned_admin_id ?? null,
      created_by_id: "preview-admin",
      due_at: data.due_at ?? null,
      notes: data.notes ?? "",
      related_object_type: data.related_object_type ?? "",
      related_object_id: data.related_object_id ?? "",
      completed_at: null,
      completion_note: "",
      is_terminal: false,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    };
    setPreviewTasks((current) => [task, ...current]);
    setPreviewEvents((events) => ({
      ...events,
      [task.id]: [eventForPreview(task, "created", "", "open", "Task created in preview mode.")]
    }));
    setSelectedTaskId(task.id);
  }

  return (
    <div className="admin-content">
      {isFixturePreview ? (
        <Banner tone="info" title="Preview task data">
          This task queue uses dummy operational records. Create and update actions are local only in preview mode.
        </Banner>
      ) : null}

      <section className="admin-kpi-grid" aria-label="Task summary">
        <StatLike label="Open tasks" value={openCount} sub={`${baseTasks.length} total returned`} />
        <StatLike label="Urgent tasks" value={urgentCount} sub="Non-terminal urgent priority" />
        <StatLike label="Due today" value={dueTodayCount} sub="Europe/Zurich operating day" />
        <StatLike label="Visible after filters" value={tasks.length} sub="Current task table" />
      </section>

      <Card padded className="admin-task-toolbar">
        <div>
          <h2>Operational task queue</h2>
          <p>Filter, create and update simple admin tasks. Detailed module actions remain in their owning screens.</p>
        </div>
        <div className="row gap-8 wrap">
          <Button icon="refresh" onClick={() => refetchLive(tasksQuery.refetch)} size="sm">
            Refresh
          </Button>
          <Button icon="plus" onClick={() => setCreating(true)} size="sm" variant="primary">
            New task
          </Button>
        </div>
      </Card>

      <Card padded>
        <div className="admin-task-filters">
          <Field label="Status">
            <select
              onChange={(event) => setFilters((current) => ({ ...current, status: event.target.value as TaskFilters["status"] }))}
              value={filters.status}
            >
              <option value="">All statuses</option>
              {taskStatusOptions.map((status) => (
                <option key={status} value={status}>{labelize(status)}</option>
              ))}
            </select>
          </Field>
          <Field label="Priority">
            <select
              onChange={(event) => setFilters((current) => ({ ...current, priority: event.target.value as TaskFilters["priority"] }))}
              value={filters.priority}
            >
              <option value="">All priorities</option>
              {taskPriorityOptions.map((priority) => (
                <option key={priority} value={priority}>{labelize(priority)}</option>
              ))}
            </select>
          </Field>
          <Field label="Type">
            <select
              onChange={(event) => setFilters((current) => ({ ...current, taskType: event.target.value as TaskFilters["taskType"] }))}
              value={filters.taskType}
            >
              <option value="">All types</option>
              {taskTypeOptions.map((taskType) => (
                <option key={taskType} value={taskType}>{labelize(taskType)}</option>
              ))}
            </select>
          </Field>
          <Field label="Search">
            <input
              onChange={(event) => setFilters((current) => ({ ...current, search: event.target.value }))}
              placeholder="Title, notes, object id"
              value={filters.search}
            />
          </Field>
        </div>
      </Card>

      {tasksQuery.error && !isFixturePreview ? (
        <Banner
          actions={<Button icon="refresh" onClick={() => refetchLive(tasksQuery.refetch)} size="sm">Retry</Button>}
          tone="bad"
          title="Could not load tasks"
        >
          {errorMessage(tasksQuery.error)}
        </Banner>
      ) : null}

      <Card className="admin-queue-panel">
        {tasks.length ? (
          <div className="table-wrap admin-table-wrap">
            <table className="admin-table admin-task-table">
              <thead>
                <tr>
                  <th>Task</th>
                  <th>Status</th>
                  <th>Priority</th>
                  <th>Due</th>
                  <th>Related object</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {tasks.map((task) => (
                  <tr key={task.id} onClick={() => setSelectedTaskId(task.id)}>
                    <td>
                      <button className="admin-row-button" type="button">
                        <strong>{task.title}</strong>
                        <span>{labelize(task.task_type)}</span>
                      </button>
                    </td>
                    <td><Chip status={task.status} tone={statusTone(task.status)}>{labelize(task.status)}</Chip></td>
                    <td><Chip dot={false} tone={priorityTone(task.priority)}>{labelize(task.priority)}</Chip></td>
                    <td className="mono">{formatDateTime(task.due_at)}</td>
                    <td>
                      {task.related_object_type ? (
                        <>
                          <span className="admin-object">{task.related_object_type}</span>
                          <span className="mono muted">{task.related_object_id}</span>
                        </>
                      ) : (
                        <span className="muted">-</span>
                      )}
                    </td>
                    <td className="mono">{formatDateTime(task.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty icon="checkCircle" title="No tasks match these filters">
            Adjust the filters or create a new internal task.
          </Empty>
        )}
      </Card>

      {creating ? (
        <CreateTaskModal
          onClose={() => setCreating(false)}
          onCreated={(task) => {
            setCreating(false);
            if (task) setSelectedTaskId(task.id);
          }}
          onPreviewCreate={createPreviewTask}
          refetchTasks={() => refetchLive(tasksQuery.refetch)}
        />
      ) : null}

      {selectedTask ? (
        <TaskDetailDrawer
          events={selectedEvents}
          eventsLoading={eventsQuery.isLoading}
          onClose={() => setSelectedTaskId(null)}
          onPreviewUpdate={updatePreviewTask}
          refetchEvents={() => refetchLive(eventsQuery.refetch)}
          refetchTasks={() => refetchLive(tasksQuery.refetch)}
          task={selectedTask}
        />
      ) : null}
    </div>
  );
}

function StatLike({ label, value, sub }: { label: string; value: number; sub: string }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      <div className="stat-sub">{sub}</div>
    </div>
  );
}

function CreateTaskModal({
  onClose,
  onCreated,
  onPreviewCreate,
  refetchTasks
}: {
  onClose: () => void;
  onCreated: (task: AdminTask | null) => void;
  onPreviewCreate: (data: AdminTaskCreateRequest) => void;
  refetchTasks: () => void;
}) {
  const createTask = useV1AdminOpsTasksCreate();
  const [taskType, setTaskType] = useState<AdminTaskTypeEnum>("other");
  const [priority, setPriority] = useState<AdminTaskPriorityEnum>("normal");
  const [title, setTitle] = useState("");
  const [dueAt, setDueAt] = useState("");
  const [notes, setNotes] = useState("");
  const [relatedObjectType, setRelatedObjectType] = useState("");
  const [relatedObjectId, setRelatedObjectId] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    const payload: AdminTaskCreateRequest = {
      task_type: taskType,
      title,
      priority,
      due_at: localValueToIso(dueAt),
      notes,
      related_object_type: relatedObjectType,
      related_object_id: relatedObjectId
    };

    if (isFixturePreview) {
      onPreviewCreate(payload);
      onClose();
      return;
    }

    createTask.mutate(
      { data: payload },
      {
        onSuccess: (task) => {
          refetchTasks();
          onCreated(task);
          onClose();
        }
      }
    );
  }

  return (
    <Modal title="New admin task" onClose={onClose} wide>
      <form className="admin-task-form" onSubmit={submit}>
        <Field label="Title">
          <input
            maxLength={255}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Describe the operational action"
            required
            value={title}
          />
        </Field>
        <div className="grid grid-3">
          <Field label="Type">
            <select onChange={(event) => setTaskType(event.target.value as AdminTaskTypeEnum)} value={taskType}>
              {taskTypeOptions.map((option) => (
                <option key={option} value={option}>{labelize(option)}</option>
              ))}
            </select>
          </Field>
          <Field label="Priority">
            <select onChange={(event) => setPriority(event.target.value as AdminTaskPriorityEnum)} value={priority}>
              {taskPriorityOptions.map((option) => (
                <option key={option} value={option}>{labelize(option)}</option>
              ))}
            </select>
          </Field>
          <Field label="Due at">
            <input onChange={(event) => setDueAt(event.target.value)} type="datetime-local" value={dueAt} />
          </Field>
        </div>
        <div className="grid grid-2">
          <Field label="Related object type">
            <input
              maxLength={128}
              onChange={(event) => setRelatedObjectType(event.target.value)}
              placeholder="loan, bank_operation, kyc_case"
              value={relatedObjectType}
            />
          </Field>
          <Field label="Related object id">
            <input
              maxLength={128}
              onChange={(event) => setRelatedObjectId(event.target.value)}
              placeholder="Internal identifier"
              value={relatedObjectId}
            />
          </Field>
        </div>
        <Field label="Notes">
          <textarea
            onChange={(event) => setNotes(event.target.value)}
            placeholder="Operational context, evidence reference, or next action"
            rows={5}
            value={notes}
          />
        </Field>
        {createTask.error ? (
          <Banner tone="bad" title="Could not create task">
            {errorMessage(createTask.error)}
          </Banner>
        ) : null}
        <div className="modal-foot inline-foot">
          <Button onClick={onClose} variant="ghost">Cancel</Button>
          <Button disabled={createTask.isPending} type="submit" variant="primary">Create task</Button>
        </div>
      </form>
    </Modal>
  );
}

function TaskDetailDrawer({
  task,
  events,
  eventsLoading,
  onClose,
  onPreviewUpdate,
  refetchEvents,
  refetchTasks
}: {
  task: AdminTask;
  events: AdminTaskEvent[];
  eventsLoading: boolean;
  onClose: () => void;
  onPreviewUpdate: (taskId: string, changes: PatchedAdminTaskUpdateRequest) => void;
  refetchEvents: () => void;
  refetchTasks: () => void;
}) {
  const updateTask = useV1AdminOpsTasksPartialUpdate();
  const [draft, setDraft] = useState({
    title: task.title,
    task_type: task.task_type as AdminTaskTypeEnum,
    priority: task.priority as AdminTaskPriorityEnum,
    status: task.status as AdminTaskStatusEnum,
    due_at: dueLocalValue(task.due_at),
    notes: task.notes,
    completion_note: task.completion_note
  });

  useEffect(() => {
    setDraft({
      title: task.title,
      task_type: task.task_type as AdminTaskTypeEnum,
      priority: task.priority as AdminTaskPriorityEnum,
      status: task.status as AdminTaskStatusEnum,
      due_at: dueLocalValue(task.due_at),
      notes: task.notes,
      completion_note: task.completion_note
    });
  }, [task]);

  function submitUpdate(event?: FormEvent, override?: Partial<typeof draft>) {
    event?.preventDefault();
    const next = { ...draft, ...override };
    const payload: PatchedAdminTaskUpdateRequest = {
      title: next.title,
      task_type: next.task_type,
      priority: next.priority,
      status: next.status,
      due_at: localValueToIso(next.due_at),
      clear_due_at: next.due_at === "",
      notes: next.notes,
      completion_note: next.completion_note
    };

    if (isFixturePreview) {
      onPreviewUpdate(task.id, payload);
      return;
    }

    updateTask.mutate(
      { taskId: task.id, data: payload },
      {
        onSuccess: () => {
          refetchTasks();
          refetchEvents();
        }
      }
    );
  }

  function quickStatus(status: AdminTaskStatusEnum) {
    setDraft((current) => ({ ...current, status }));
    submitUpdate(undefined, { status });
  }

  return (
    <Modal drawer title={task.title} onClose={onClose}>
      <form className="admin-drawer-body" onSubmit={submitUpdate}>
        <div className="row gap-8 wrap">
          <Chip status={task.status} tone={statusTone(task.status)}>{labelize(task.status)}</Chip>
          <Chip dot={false} tone={priorityTone(task.priority)}>{labelize(task.priority)}</Chip>
          <Chip dot={false} tone={task.is_terminal ? "neutral" : "info"}>
            {task.is_terminal ? "Terminal" : "Open"}
          </Chip>
        </div>

        <div className="admin-detail-grid">
          <ReviewRow label="Task ID" value={task.id} />
          <ReviewRow label="Created" value={formatDateTime(task.created_at)} />
          <ReviewRow label="Updated" value={formatDateTime(task.updated_at)} />
          <ReviewRow label="Related object" value={task.related_object_type ? `${task.related_object_type} / ${task.related_object_id}` : "-"} />
        </div>

        <Field label="Title">
          <input
            maxLength={255}
            onChange={(event) => setDraft((current) => ({ ...current, title: event.target.value }))}
            required
            value={draft.title}
          />
        </Field>

        <div className="grid grid-2">
          <Field label="Status">
            <select onChange={(event) => setDraft((current) => ({ ...current, status: event.target.value as AdminTaskStatusEnum }))} value={draft.status}>
              {taskStatusOptions.map((status) => (
                <option key={status} value={status}>{labelize(status)}</option>
              ))}
            </select>
          </Field>
          <Field label="Priority">
            <select onChange={(event) => setDraft((current) => ({ ...current, priority: event.target.value as AdminTaskPriorityEnum }))} value={draft.priority}>
              {taskPriorityOptions.map((priority) => (
                <option key={priority} value={priority}>{labelize(priority)}</option>
              ))}
            </select>
          </Field>
        </div>

        <div className="grid grid-2">
          <Field label="Type">
            <select onChange={(event) => setDraft((current) => ({ ...current, task_type: event.target.value as AdminTaskTypeEnum }))} value={draft.task_type}>
              {taskTypeOptions.map((taskType) => (
                <option key={taskType} value={taskType}>{labelize(taskType)}</option>
              ))}
            </select>
          </Field>
          <Field label="Due at">
            <input onChange={(event) => setDraft((current) => ({ ...current, due_at: event.target.value }))} type="datetime-local" value={draft.due_at} />
          </Field>
        </div>

        <Field label="Notes">
          <textarea
            onChange={(event) => setDraft((current) => ({ ...current, notes: event.target.value }))}
            rows={5}
            value={draft.notes}
          />
        </Field>

        {isTerminalStatus(draft.status) ? (
          <Field label="Completion note">
            <textarea
              onChange={(event) => setDraft((current) => ({ ...current, completion_note: event.target.value }))}
              placeholder="Document how this task was resolved or why it was cancelled."
              rows={3}
              value={draft.completion_note}
            />
          </Field>
        ) : null}

        {updateTask.error ? (
          <Banner tone="bad" title="Could not update task">
            {errorMessage(updateTask.error)}
          </Banner>
        ) : null}

        <div className="admin-action-row">
          <Button onClick={() => quickStatus("in_progress")} size="sm" variant="ghost">Mark in progress</Button>
          <Button onClick={() => quickStatus("waiting")} size="sm" variant="ghost">Waiting</Button>
          <Button onClick={() => quickStatus("resolved")} size="sm" variant="primary">Resolve</Button>
          <Button onClick={() => quickStatus("cancelled")} size="sm" variant="danger">Cancel task</Button>
        </div>

        <div className="row gap-8">
          <Button disabled={updateTask.isPending} type="submit" variant="primary">Save changes</Button>
          <Button onClick={onClose} variant="ghost">Close</Button>
        </div>

        <div>
          <div className="admin-dashboard-head" style={{ marginBottom: 8 }}>
            <div>
              <h4>Task event history</h4>
              <p>Append-only lifecycle evidence returned by the admin operations API.</p>
            </div>
            <Button icon="refresh" onClick={refetchEvents} size="sm" variant="ghost">Refresh</Button>
          </div>
          {eventsLoading && !events.length ? (
            <p className="muted">Loading task events...</p>
          ) : events.length ? (
            <div className="admin-task-events">
              {events.map((event) => (
                <div className="admin-task-event" key={event.id}>
                  <div>
                    <strong>{labelize(event.event_type)}</strong>
                    <span className="mono muted">{formatDateTime(event.occurred_at)}</span>
                  </div>
                  <p>{event.note || "No note."}</p>
                  <span className="muted">
                    {labelize(event.previous_status)} → {labelize(event.new_status)} by {event.actor_account_type}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <Empty icon="clock" title="No task events">
              This task has no event history returned by the API.
            </Empty>
          )}
        </div>
      </form>
    </Modal>
  );
}

function ReviewRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="admin-review-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
