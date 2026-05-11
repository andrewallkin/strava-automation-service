import { ChangeEvent, FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ConfirmDialog } from "../components/ConfirmDialog";
import {
  VECTOR_STORE_MAX_FILE_BYTES,
  VectorStore,
  VectorStoreFileRow,
  createVectorStore,
  fetchCoachSettings,
  deleteVectorStore,
  deleteVectorStoreFile,
  fetchVectorStore,
  fetchVectorStoreFiles,
  fetchVectorStores,
  updateCoachSettings,
  uploadVectorStoreFile,
} from "../lib/api";

type PendingConfirm =
  | { type: "removeFile"; row: VectorStoreFileRow }
  | { type: "deleteStore" };

const ALLOWED_EXTENSIONS = new Set([".pdf", ".md", ".markdown"]);

/** Set before full reload after delete; read on next load to show toast. */
const VECTOR_STORE_DELETED_TOAST_KEY = "strava_vector_store_deleted_toast";

function formatUnix(ts: number | null): string {
  if (ts == null) return "-";
  return new Date(ts * 1000).toLocaleString();
}

function fileCountsLabel(store: VectorStore): string {
  const fc = store.file_counts;
  if (!fc || typeof fc !== "object") return "-";
  const total = fc.total;
  if (typeof total === "number") return String(total);
  const c = fc.completed;
  const ip = fc.in_progress;
  if (typeof c === "number" || typeof ip === "number") {
    return `${c ?? 0} done${typeof ip === "number" && ip > 0 ? `, ${ip} in progress` : ""}`;
  }
  return "-";
}

export function VectorStorePage() {
  const [stores, setStores] = useState<VectorStore[]>([]);
  const [storeLoading, setStoreLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<VectorStore | null>(null);
  const [files, setFiles] = useState<VectorStoreFileRow[]>([]);
  const [filesLoading, setFilesLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [newStoreName, setNewStoreName] = useState("");
  const [creating, setCreating] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [pendingConfirm, setPendingConfirm] = useState<PendingConfirm | null>(null);
  const [confirmBusy, setConfirmBusy] = useState(false);
  const [coachVectorStoreId, setCoachVectorStoreId] = useState<string | null>(null);
  const [coachSaveBusy, setCoachSaveBusy] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadStores = useCallback(async () => {
    setStoreLoading(true);
    setError(null);
    try {
      const res = await fetchVectorStores({ limit: 50 });
      setStores(res.data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load vector stores");
      setStores([]);
    } finally {
      setStoreLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadStores();
  }, [loadStores]);

  useEffect(() => {
    fetchCoachSettings()
      .then((settings) => setCoachVectorStoreId(settings.vector_store_id))
      .catch(() => {
        /* ignore when not configured */
      });
  }, []);

  useEffect(() => {
    try {
      if (sessionStorage.getItem(VECTOR_STORE_DELETED_TOAST_KEY) === "1") {
        sessionStorage.removeItem(VECTOR_STORE_DELETED_TOAST_KEY);
        setMessage("Vector store deleted");
      }
    } catch {
      /* ignore private mode / quota */
    }
  }, []);

  useEffect(() => {
    if (!message) return;
    const t = window.setTimeout(() => setMessage(null), 5000);
    return () => window.clearTimeout(t);
  }, [message]);

  const loadSelected = useCallback(async (id: string) => {
    setFilesLoading(true);
    setError(null);
    try {
      const [detail, fileList] = await Promise.all([
        fetchVectorStore(id),
        fetchVectorStoreFiles(id, { limit: 100 }),
      ]);
      setSelectedDetail(detail);
      setFiles(fileList.data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load store");
      setSelectedDetail(null);
      setFiles([]);
    } finally {
      setFilesLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setSelectedDetail(null);
      setFiles([]);
      return;
    }
    void loadSelected(selectedId);
  }, [selectedId, loadSelected]);

  const onCreate = async (e: FormEvent) => {
    e.preventDefault();
    setCreating(true);
    setMessage(null);
    setError(null);
    try {
      const s = await createVectorStore(newStoreName || null);
      setNewStoreName("");
      setMessage(`Created vector store ${s.id}`);
      await loadStores();
      setSelectedId(s.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    } finally {
      setCreating(false);
    }
  };

  const onPickFile = () => fileInputRef.current?.click();

  const onFileChange = async (e: ChangeEvent<HTMLInputElement>) => {
    const list = e.target.files;
    const file = list?.[0];
    e.target.value = "";
    if (!file || !selectedId) return;

    const lower = file.name.toLowerCase();
    const okExt = [...ALLOWED_EXTENSIONS].some((ext) => lower.endsWith(ext));
    if (!okExt) {
      setError("Only .pdf, .md, and .markdown files are allowed.");
      return;
    }
    if (file.size > VECTOR_STORE_MAX_FILE_BYTES) {
      setError(`File must be at most ${VECTOR_STORE_MAX_FILE_BYTES / (1024 * 1024)} MB.`);
      return;
    }

    setUploading(true);
    setError(null);
    setMessage(null);
    try {
      await uploadVectorStoreFile(selectedId, file);
      setMessage(`Uploaded ${file.name}`);
      await loadSelected(selectedId);
      await loadStores();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const onRemoveFile = (row: VectorStoreFileRow) => {
    if (!selectedId) return;
    setError(null);
    setMessage(null);
    setPendingConfirm({ type: "removeFile", row });
  };

  const onDeleteStore = () => {
    if (!selectedId || !selectedDetail) return;
    setError(null);
    setMessage(null);
    setPendingConfirm({ type: "deleteStore" });
  };

  const onUseStoreForCoach = async () => {
    if (!selectedId) return;
    setCoachSaveBusy(true);
    setError(null);
    setMessage(null);
    try {
      const next = await updateCoachSettings({ vector_store_id: selectedId });
      setCoachVectorStoreId(next.vector_store_id);
      setMessage("Coach bot now uses this vector store");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save coach vector store");
    } finally {
      setCoachSaveBusy(false);
    }
  };

  const runConfirmedAction = async () => {
    if (!pendingConfirm || !selectedId) return;
    setConfirmBusy(true);
    setError(null);
    setMessage(null);
    try {
      if (pendingConfirm.type === "removeFile") {
        const removedFileId = pendingConfirm.row.file_id;
        await deleteVectorStoreFile(selectedId, removedFileId);
        setFiles((prev) => prev.filter((r) => r.file_id !== removedFileId));
        setMessage("File removed");
        await loadSelected(selectedId);
        await loadStores();
      } else {
        await deleteVectorStore(selectedId);
        try {
          sessionStorage.setItem(VECTOR_STORE_DELETED_TOAST_KEY, "1");
        } catch {
          /* ignore */
        }
        setPendingConfirm(null);
        window.location.reload();
        return;
      }
      setPendingConfirm(null);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : pendingConfirm.type === "removeFile"
            ? "Remove failed"
            : "Delete store failed"
      );
    } finally {
      setConfirmBusy(false);
    }
  };

  const deleteStoreLabel = selectedDetail?.name?.trim() || selectedDetail?.id || "";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Vector stores</h1>
        <p className="text-sm text-gray-500 mt-1">
          Manage OpenAI vector stores and uploaded documents (markdown and PDF only, max 10&nbsp;MB).
          Use a store ID in your agent or notebook{" "}
          <code className="text-xs bg-gray-100 px-1 rounded">VECTOR_STORE_ID</code> environment
          variable. You can also assign a store directly to your coach bot from this page.
        </p>
      </div>

      {message && (
        <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
          {message}
        </div>
      )}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between gap-3">
            <h2 className="text-base font-semibold text-gray-900">Your stores</h2>
            <button
              type="button"
              onClick={() => void loadStores()}
              className="text-sm font-medium text-orange-600 hover:text-orange-700"
            >
              Refresh
            </button>
          </div>
          <div className="p-5 space-y-4">
            <form onSubmit={(ev) => void onCreate(ev)} className="flex flex-wrap gap-2 items-end">
              <div className="flex-1 min-w-[12rem]">
                <label htmlFor="vs-name" className="block text-xs font-medium text-gray-500 mb-1">
                  New store name (optional)
                </label>
                <input
                  id="vs-name"
                  type="text"
                  value={newStoreName}
                  onChange={(ev) => setNewStoreName(ev.target.value)}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                  placeholder="e.g. Training plan"
                />
              </div>
              <button
                type="submit"
                disabled={creating}
                className="px-4 py-2 rounded-md bg-orange-500 text-white text-sm font-medium hover:bg-orange-600 disabled:opacity-50"
              >
                {creating ? "Creating…" : "Create store"}
              </button>
            </form>

            {storeLoading ? (
              <p className="text-sm text-gray-500">Loading…</p>
            ) : stores.length === 0 ? (
              <p className="text-sm text-gray-500">No vector stores yet. Create one above.</p>
            ) : (
              <ul className="divide-y divide-gray-100 border border-gray-100 rounded-lg max-h-80 overflow-y-auto">
                {stores.map((s) => (
                  <li key={s.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedId(s.id)}
                      className={`w-full text-left px-4 py-3 text-sm transition-colors ${
                        selectedId === s.id
                          ? "bg-orange-50 border-l-4 border-l-orange-500"
                          : "hover:bg-gray-50 border-l-4 border-l-transparent"
                      }`}
                    >
                      <div className="font-medium text-gray-900 break-all">{s.name || "(unnamed)"}</div>
                      <div className="text-xs text-gray-500 mt-0.5 break-all font-mono">{s.id}</div>
                      <div className="text-xs text-gray-400 mt-1">
                        Status: {s.status ?? "-"} · Files: {fileCountsLabel(s)}
                      </div>
                      {coachVectorStoreId === s.id && (
                        <div className="text-xs text-orange-700 mt-1 font-medium">Coach bot store</div>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200">
          <div className="px-5 py-4 border-b border-gray-100">
            <h2 className="text-base font-semibold text-gray-900">Store detail</h2>
          </div>
          <div className="p-5 space-y-4">
            {!selectedId ? (
              <p className="text-sm text-gray-500">Select a vector store to view files and upload.</p>
            ) : filesLoading ? (
              <p className="text-sm text-gray-500">Loading store…</p>
            ) : (
              <>
                {selectedDetail && (
                  <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
                    <dt className="text-gray-500">ID</dt>
                    <dd className="font-mono text-xs break-all">{selectedDetail.id}</dd>
                    <dt className="text-gray-500">Name</dt>
                    <dd>{selectedDetail.name || "—"}</dd>
                    <dt className="text-gray-500">Status</dt>
                    <dd>{selectedDetail.status ?? "—"}</dd>
                    <dt className="text-gray-500">Created</dt>
                    <dd>{formatUnix(selectedDetail.created_at)}</dd>
                  </dl>
                )}

                {selectedId && (
                  <div className="rounded-lg border border-orange-200 bg-orange-50/70 px-3 py-3 space-y-2">
                    <p className="text-xs text-orange-900 font-medium">
                      {coachVectorStoreId === selectedId
                        ? "This store is currently used by your coach bot."
                        : "Use this store as the coach bot knowledge base."}
                    </p>
                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        onClick={() => void onUseStoreForCoach()}
                        disabled={coachSaveBusy || coachVectorStoreId === selectedId}
                        className="px-3 py-1.5 rounded-md bg-orange-500 text-white text-xs font-medium hover:bg-orange-600 disabled:opacity-50"
                      >
                        {coachSaveBusy ? "Saving…" : "Use for coach"}
                      </button>
                      <Link
                        to="/settings"
                        className="px-3 py-1.5 rounded-md bg-white border border-orange-200 text-xs font-medium text-orange-700 hover:bg-orange-100"
                      >
                        Open coach settings
                      </Link>
                    </div>
                  </div>
                )}

                <div className="pt-2 border-t border-gray-100">
                  <button
                    type="button"
                    onClick={onDeleteStore}
                    disabled={confirmBusy}
                    className="text-sm font-medium text-red-600 hover:text-red-800 disabled:opacity-50"
                  >
                    {confirmBusy && pendingConfirm?.type === "deleteStore"
                      ? "Deleting…"
                      : "Delete vector store"}
                  </button>
                  <p className="text-xs text-gray-500 mt-1">
                    Permanently removes this store in OpenAI. Update{" "}
                    <code className="text-[11px] bg-gray-100 px-1 rounded">VECTOR_STORE_ID</code> if
                    your agent used this store.
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf,.md,.markdown,application/pdf,text/markdown"
                    className="hidden"
                    onChange={(ev) => void onFileChange(ev)}
                  />
                  <button
                    type="button"
                    onClick={onPickFile}
                    disabled={uploading || confirmBusy}
                    className="px-4 py-2 rounded-md border border-gray-300 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                  >
                    {uploading ? "Uploading…" : "Upload PDF or Markdown"}
                  </button>
                  <span className="text-xs text-gray-500">Max 10 MB</span>
                </div>

                {files.length === 0 ? (
                  <p className="text-sm text-gray-500">No files attached yet.</p>
                ) : (
                  <div className="overflow-x-auto border border-gray-100 rounded-lg">
                    <table className="min-w-full text-sm">
                      <thead className="bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                        <tr>
                          <th className="px-3 py-2">File</th>
                          <th className="px-3 py-2">Status</th>
                          <th className="px-3 py-2">Added</th>
                          <th className="px-3 py-2 w-24" />
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {files.map((row) => (
                          <tr key={row.file_id}>
                            <td className="px-3 py-2">
                              <div className="font-medium text-gray-900 break-all">
                                {row.filename ?? row.file_id}
                              </div>
                              <div className="text-xs text-gray-400 font-mono break-all">
                                {row.file_id}
                              </div>
                            </td>
                            <td className="px-3 py-2 text-gray-600">{row.status ?? "—"}</td>
                            <td className="px-3 py-2 text-gray-600 whitespace-nowrap">
                              {formatUnix(row.created_at)}
                            </td>
                            <td className="px-3 py-2">
                              <button
                                type="button"
                                onClick={() => onRemoveFile(row)}
                                disabled={confirmBusy}
                                className="text-red-600 hover:text-red-800 text-xs font-medium disabled:opacity-50"
                              >
                                Remove
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      <ConfirmDialog
        open={pendingConfirm !== null}
        title={
          pendingConfirm?.type === "removeFile"
            ? "Remove file from store?"
            : "Delete vector store?"
        }
        description={
          pendingConfirm?.type === "removeFile" ? (
            <p>
              Remove {pendingConfirm.row.filename ?? pendingConfirm.row.file_id} from this vector
              store?
            </p>
          ) : selectedDetail ? (
            <>
              <p>
                Delete vector store &quot;{deleteStoreLabel}&quot; ({selectedDetail.id})?
              </p>
              <p>
                This removes the store and its file links in OpenAI. Uploaded files may still exist
                in your OpenAI project until removed separately. This cannot be undone.
              </p>
            </>
          ) : null
        }
        confirmLabel={pendingConfirm?.type === "removeFile" ? "Remove" : "Delete"}
        cancelLabel="Cancel"
        variant="danger"
        loading={confirmBusy}
        onCancel={() => {
          if (!confirmBusy) setPendingConfirm(null);
        }}
        onConfirm={() => void runConfirmedAction()}
      />
    </div>
  );
}
