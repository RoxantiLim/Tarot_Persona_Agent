import { apiPost } from "@/lib/api";
import {
  addKnowledgeHistoryItem,
  buildKnowledgeQuery,
  saveKnowledgeState,
  type KnowledgeSavedState,
} from "@/lib/knowledge-storage";
import type { KnowledgeResponse } from "@/lib/types";

type KnowledgeTaskSnapshot =
  | { status: "idle" }
  | { status: "running"; taskId: string; startedAt: string; state: KnowledgeSavedState }
  | { status: "success"; taskId: string; finishedAt: string; state: KnowledgeSavedState; result: KnowledgeResponse }
  | { status: "error"; taskId: string; finishedAt: string; state: KnowledgeSavedState; message: string };

type KnowledgeTaskSubscriber = () => void;

const idleKnowledgeTaskSnapshot: KnowledgeTaskSnapshot = { status: "idle" };
let taskSnapshot: KnowledgeTaskSnapshot = idleKnowledgeTaskSnapshot;
const subscribers = new Set<KnowledgeTaskSubscriber>();

function emitTaskChange() {
  subscribers.forEach((subscriber) => subscriber());
}

export function subscribeKnowledgeTask(subscriber: KnowledgeTaskSubscriber) {
  subscribers.add(subscriber);
  return () => subscribers.delete(subscriber);
}

export function getKnowledgeTaskSnapshot() {
  return taskSnapshot;
}

export function getKnowledgeTaskServerSnapshot(): KnowledgeTaskSnapshot {
  return idleKnowledgeTaskSnapshot;
}

export function resetKnowledgeTask() {
  taskSnapshot = idleKnowledgeTaskSnapshot;
  emitTaskChange();
}

export function startKnowledgeTask(state: KnowledgeSavedState) {
  if (taskSnapshot.status === "running") {
    return taskSnapshot;
  }

  const taskId = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const taskState: KnowledgeSavedState = { ...state, result: null };

  taskSnapshot = {
    status: "running",
    taskId,
    startedAt: new Date().toISOString(),
    state: taskState,
  };
  saveKnowledgeState(taskState);
  emitTaskChange();

  apiPost<KnowledgeResponse>("/api/knowledge/query", {
    mode: taskState.mode,
    query: buildKnowledgeQuery(taskState),
    card_name: taskState.cardName,
    orientation: taskState.orientation,
    topic: taskState.topic,
    top_k: taskState.topK,
  })
    .then((result) => {
      const finishedState = { ...taskState, result };
      saveKnowledgeState(finishedState);
      addKnowledgeHistoryItem(finishedState, result);
      taskSnapshot = {
        status: "success",
        taskId,
        finishedAt: new Date().toISOString(),
        state: finishedState,
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
        message: error instanceof Error ? error.message : "暂时无法查询，请稍后再试。",
      };
      emitTaskChange();
    });

  return taskSnapshot;
}
