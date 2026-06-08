import { apiPost } from "@/lib/api";
import { addReadingHistoryItem, saveReadingState, type ReadingSavedState } from "@/lib/reading-storage";
import type { ReadingResponse } from "@/lib/types";

type ReadingTaskSnapshot =
  | { status: "idle" }
  | { status: "running"; taskId: string; startedAt: string; state: ReadingSavedState; readerName: string }
  | { status: "success"; taskId: string; finishedAt: string; state: ReadingSavedState; readerName: string; result: ReadingResponse }
  | { status: "error"; taskId: string; finishedAt: string; state: ReadingSavedState; readerName: string; message: string };

type ReadingTaskSubscriber = () => void;

const idleReadingTaskSnapshot: ReadingTaskSnapshot = { status: "idle" };
let taskSnapshot: ReadingTaskSnapshot = idleReadingTaskSnapshot;
const subscribers = new Set<ReadingTaskSubscriber>();

function emitTaskChange() {
  subscribers.forEach((subscriber) => subscriber());
}

export function subscribeReadingTask(subscriber: ReadingTaskSubscriber) {
  subscribers.add(subscriber);
  return () => subscribers.delete(subscriber);
}

export function getReadingTaskSnapshot() {
  return taskSnapshot;
}

export function getReadingTaskServerSnapshot(): ReadingTaskSnapshot {
  return idleReadingTaskSnapshot;
}

export function resetReadingTask() {
  taskSnapshot = idleReadingTaskSnapshot;
  emitTaskChange();
}

export function startReadingTask(state: ReadingSavedState, readerName: string) {
  if (taskSnapshot.status === "running") {
    return taskSnapshot;
  }

  const taskId = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const taskState: ReadingSavedState = {
    ...state,
    selectedCards: state.selectedCards.map((card) => ({ ...card })),
    result: null,
  };

  taskSnapshot = {
    status: "running",
    taskId,
    startedAt: new Date().toISOString(),
    state: taskState,
    readerName,
  };
  saveReadingState(taskState);
  emitTaskChange();

  apiPost<ReadingResponse>("/api/reading/generate", {
    reader_id: taskState.readerId,
    question: taskState.question,
    cards: taskState.selectedCards,
    include_check: false,
  })
    .then((result) => {
      const finishedState = { ...taskState, result };
      saveReadingState(finishedState);
      addReadingHistoryItem(finishedState, readerName, result);
      taskSnapshot = {
        status: "success",
        taskId,
        finishedAt: new Date().toISOString(),
        state: finishedState,
        readerName,
        result,
      };
      emitTaskChange();
    })
    .catch((error: unknown) => {
      taskSnapshot = {
        status: "error",
        taskId,
        finishedAt: new Date().toISOString(),
        state: taskState,
        readerName,
        message: error instanceof Error ? error.message : "暂时无法生成解读，请稍后再试。",
      };
      emitTaskChange();
    });

  return taskSnapshot;
}
