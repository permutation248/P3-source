import { useState, useEffect, useCallback } from 'react';
import { Upload as UploadIcon, FolderOpen, FileText } from 'lucide-react';
import {
  PageHeader,
  SectionCard,
  FormField,
  LoadingSpinner,
  inputClass,
  btnPrimary,
} from '../components/shared';

interface Dataset {
  name: string;
  path: string;
  tasks_mode?: 'file' | 'project';
  task_count: number;
  task_count_file?: number;
  task_count_project?: number;
}

interface PreparedFile {
  file: File;
  rel: string;
}

const isHiddenPath = (path: string): boolean =>
  path.split('/').some((segment) => segment.startsWith('.'));

const prepareFiles = (list: FileList): PreparedFile[] => {
  const prepared: PreparedFile[] = [];
  for (let i = 0; i < list.length; i++) {
    const file = list[i] as File & { webkitRelativePath?: string };
    const rel = file.webkitRelativePath && file.webkitRelativePath.length > 0
      ? file.webkitRelativePath
      : file.name;
    if (isHiddenPath(rel)) continue;
    prepared.push({ file, rel });
  }
  return prepared;
};

export default function Upload() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState('');
  const [tasksMode, setTasksMode] = useState<'file' | 'project'>('file');
  const [files, setFiles] = useState<PreparedFile[]>([]);
  const [hiddenSkipped, setHiddenSkipped] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const loadDatasets = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/datasets');
      const data = await res.json();
      setDatasets(data);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDatasets();
  }, [loadDatasets]);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setMessage({ type: 'error', text: 'Dataset name is required' });
      return;
    }
    if (files.length === 0) {
      setMessage({ type: 'error', text: 'Please select files or a folder' });
      return;
    }

    setUploading(true);
    setMessage(null);

    const formData = new FormData();
    formData.append('name', name.trim());
    formData.append('tasks_mode', tasksMode);

    for (const { file, rel } of files) {
      formData.append('files', file, rel);
    }

    try {
      const res = await fetch('/api/datasets', {
        method: 'POST',
        body: formData,
      });
      if (!res.ok) {
        const body = await res.json();
        throw new Error(body.detail || `Upload failed (${res.status})`);
      }
      const result = await res.json();
      setMessage({
        type: 'success',
        text: `Uploaded to ${result.path}. mode=${result.tasks_mode}, tasks=${result.task_count}`,
      });
      setName('');
      setTasksMode('file');
      setFiles([]);
      setHiddenSkipped(0);
      const fileInput = document.getElementById('file-input') as HTMLInputElement;
      if (fileInput) fileInput.value = '';
      loadDatasets();
    } catch (err) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Upload failed' });
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-8">
      <PageHeader
        title="Datasets"
        subtitle="Manage Lean 4 verification task datasets"
        symbol="∈"
      />

      {/* Upload form */}
      <SectionCard title="Upload New Dataset" className="mb-8">
        {message && (
          <div
            className={`mb-4 rounded-lg border px-4 py-3 text-sm ${
              message.type === 'success'
                ? 'border-emerald-200 bg-emerald-50/50 text-proof-green'
                : 'border-red-200 bg-red-50/50 text-proof-red'
            }`}
          >
            {message.text}
          </div>
        )}

        <form id="upload-form" onSubmit={handleUpload} className="space-y-5">
          <FormField label="Dataset Name">
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., my_benchmark"
              className={inputClass}
            />
          </FormField>

          <FormField label="Task Discovery Mode">
            <select
              value={tasksMode}
              onChange={(e) => setTasksMode(e.target.value === 'project' ? 'project' : 'file')}
              className={inputClass}
            >
              <option value="file">file (each .lean file is a task)</option>
              <option value="project">project (each folder with .lean files is a task)</option>
            </select>
          </FormField>

          <FormField label="Dataset Files" hint="select a folder or individual files (all file types)">
            <input
              id="file-input"
              type="file"
              multiple
              // @ts-expect-error webkitdirectory is non-standard but widely supported
              webkitdirectory=""
              onChange={(e) => {
                const list = e.target.files;
                if (!list) {
                  setFiles([]);
                  setHiddenSkipped(0);
                  return;
                }
                const prepared = prepareFiles(list);
                setFiles(prepared);
                setHiddenSkipped(list.length - prepared.length);
              }}
              className="w-full rounded-lg border border-ink-200 bg-white px-3 py-2 text-sm text-ink-500 shadow-sm file:mr-4 file:rounded-md file:border-0 file:bg-accent-50 file:px-4 file:py-1.5 file:text-sm file:font-medium file:text-accent-700 hover:file:bg-accent-100 transition-colors"
            />
            {files.length > 0 && (
              <p className="mt-1.5 font-mono text-xs text-ink-400">
                {files.length} file(s) ready to upload
                {hiddenSkipped > 0 && ` (${hiddenSkipped} hidden skipped)`}
              </p>
            )}
            {files.length === 0 && hiddenSkipped > 0 && (
              <p className="mt-1.5 font-mono text-xs text-red-500">
                All {hiddenSkipped} selected file(s) are hidden and were skipped
              </p>
            )}
          </FormField>

        </form>
      </SectionCard>

      {/* Submit */}
      <div className="flex justify-end">
        <button type="submit" form="upload-form" disabled={uploading} className={btnPrimary}>
          <UploadIcon size={16} />
          {uploading ? 'Uploading...' : 'Upload Dataset'}
        </button>
      </div>

      {/* Existing datasets */}
      <SectionCard title="Available Datasets">
        {loading ? (
          <LoadingSpinner size="sm" />
        ) : datasets.length === 0 ? (
          <div className="flex flex-col items-center py-8 text-ink-300">
            <FolderOpen size={32} className="mb-2" />
            <p className="font-mono text-sm">No datasets found in Benchmarks/</p>
          </div>
        ) : (
          <div className="space-y-2">
            {datasets.map((d) => (
              <div
                key={d.name}
                className="flex items-center justify-between rounded-lg border border-ink-100 px-4 py-3 transition-colors hover:bg-ink-50/50"
              >
                <div className="flex items-center gap-3">
                  <FileText size={16} className="text-accent-400" />
                  <div>
                    <p className="text-sm font-medium text-ink-700">{d.name}</p>
                    <p className="font-mono text-xs text-ink-400">
                      {d.path} · mode:{d.tasks_mode ?? 'file'}
                    </p>
                  </div>
                </div>
                <span className="rounded-md bg-ink-50 px-2.5 py-1 font-mono text-xs font-medium text-ink-500">
                  total:{d.task_count}
                </span>
              </div>
            ))}
          </div>
        )}
      </SectionCard>
    </div>
  );
}
