import { useEffect, useMemo, useState } from 'react';
import { Check, Eye, EyeOff, RotateCcw, Save } from 'lucide-react';
import {
  useApiKey,
  BACKEND_LABELS,
  type AgentFamily,
  type BackendChoice,
  type CredentialMap,
} from '../contexts/ApiKeyContext';
import {
  PageHeader,
  SectionCard,
  FormField,
  inputClass,
  selectClass,
  btnPrimary,
  btnSecondary,
} from '../components/shared';

type Slot = 'api' | 'miromind';

interface SlotMeta {
  label: string;
  hint: string;
  placeholder: string;
}

const CLAUDE_SLOTS: Record<Slot, SlotMeta> = {
  api: {
    label: 'Anthropic API Key',
    hint: '(sk-ant-...)',
    placeholder: 'sk-ant-api03-...',
  },
  miromind: {
    label: 'MiroMind API Key',
    hint: '(Anthropic-compatible gateway)',
    placeholder: 'mm-...',
  },
};

const CODEX_SLOTS: Record<Slot, SlotMeta> = {
  api: {
    label: 'OpenAI API Key',
    hint: '(sk-...)',
    placeholder: 'sk-...',
  },
  miromind: {
    label: 'MiroMind API Key',
    hint: '(OpenAI Responses gateway)',
    placeholder: 'mm-...',
  },
};

// All in-flight edits live in this single draft object; only the global
// Save button commits it to context (→ localStorage). No per-row saves.
interface Draft {
  credentials: CredentialMap;
  activeBackend: Record<AgentFamily, BackendChoice>;
  useDocker: boolean | null;
}

function ActiveBackendRow({
  family,
  value,
  onChange,
}: {
  family: AgentFamily;
  value: BackendChoice;
  onChange: (v: BackendChoice) => void;
}) {
  const { availableBackends, subscriptionProbed } = useApiKey();
  const options: BackendChoice[] = ['default', ...availableBackends(family)];
  return (
    <FormField
      label="Active Backend"
      hint="Used by every run (new / restart / resume) in this family."
    >
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as BackendChoice)}
        className={selectClass}
        disabled={!subscriptionProbed}
      >
        {options.map((b) => (
          <option key={b} value={b}>
            {BACKEND_LABELS[b]}
          </option>
        ))}
      </select>
    </FormField>
  );
}

function CredentialRow({
  meta,
  value,
  onChange,
}: {
  meta: SlotMeta;
  value: string;
  onChange: (v: string) => void;
}) {
  const [showKey, setShowKey] = useState(false);
  const configured = value.length > 0;

  return (
    <FormField label={meta.label} hint={meta.hint}>
      <div className="relative">
        <input
          type={showKey ? 'text' : 'password'}
          className={inputClass + ' pr-10 font-mono text-xs'}
          placeholder={meta.placeholder}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
        <button
          type="button"
          className="absolute right-2.5 top-1/2 -translate-y-1/2 text-ink-400 hover:text-ink-600"
          onClick={() => setShowKey((s) => !s)}
          aria-label={showKey ? 'Hide key' : 'Show key'}
        >
          {showKey ? <EyeOff size={16} /> : <Eye size={16} />}
        </button>
      </div>
      <div className="mt-1 text-xs">
        {configured ? (
          <span className="text-emerald-600">Configured</span>
        ) : (
          <span className="text-ink-400">Empty</span>
        )}
      </div>
    </FormField>
  );
}

function SubscriptionRow({ family }: { family: AgentFamily }) {
  const { subscriptionAvailable } = useApiKey();
  const available = subscriptionAvailable[family];
  const location =
    family === 'claude' ? '~/.claude/.credentials.json' : '~/.codex/auth.json';

  return (
    <FormField label="Subscription (OAuth)" hint="Mounted on the server">
      <div className="flex items-center gap-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5">
        <span
          className={`inline-block h-2 w-2 shrink-0 rounded-full ${
            available ? 'bg-emerald-500' : 'bg-slate-300'
          }`}
        />
        <div className="text-sm">
          <div className={available ? 'text-emerald-700' : 'text-ink-500'}>
            {available ? 'Available' : 'Not available'}
          </div>
          <div className="font-mono text-[11px] text-ink-400">{location}</div>
        </div>
      </div>
    </FormField>
  );
}

function FamilySection({
  family,
  draft,
  setDraft,
}: {
  family: AgentFamily;
  draft: Draft;
  setDraft: (next: Draft) => void;
}) {
  const title = family === 'claude' ? 'Claude' : 'Codex';
  const slots = family === 'claude' ? CLAUDE_SLOTS : CODEX_SLOTS;
  return (
    <SectionCard title={title}>
      <div className="space-y-5">
        <ActiveBackendRow
          family={family}
          value={draft.activeBackend[family]}
          onChange={(v) =>
            setDraft({
              ...draft,
              activeBackend: { ...draft.activeBackend, [family]: v },
            })
          }
        />
        <div className="border-t border-slate-200 pt-5">
          <CredentialRow
            meta={slots.api}
            value={draft.credentials[family].api}
            onChange={(v) =>
              setDraft({
                ...draft,
                credentials: {
                  ...draft.credentials,
                  [family]: { ...draft.credentials[family], api: v },
                },
              })
            }
          />
        </div>
        <CredentialRow
          meta={slots.miromind}
          value={draft.credentials[family].miromind}
          onChange={(v) =>
            setDraft({
              ...draft,
              credentials: {
                ...draft.credentials,
                [family]: { ...draft.credentials[family], miromind: v },
              },
            })
          }
        />
        <SubscriptionRow family={family} />
      </div>
    </SectionCard>
  );
}

function RuntimeSection({
  value,
  onChange,
}: {
  value: boolean | null;
  onChange: (v: boolean | null) => void;
}) {
  const checkboxValue = value === true;
  return (
    <SectionCard title="Runtime">
      <div className="space-y-3">
        <p className="text-sm text-ink-500">
          How agents execute on the server. Applies to every run.
        </p>
        <label className="flex items-start gap-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5">
          <input
            type="checkbox"
            checked={checkboxValue}
            onChange={(e) => onChange(e.target.checked)}
            className="mt-0.5 h-4 w-4 shrink-0"
          />
          <div className="text-sm">
            <div className="font-medium text-ink-700">Run agents in Docker</div>
            <div className="mt-0.5 text-xs text-ink-500">
              Check to isolate agents in containers. Uncheck on hosts that forbid
              Docker-in-Docker (e.g., PAI-DSW) — the harness runs natively instead.
              Click "Reset to server default" to follow{' '}
              <code>ANONYMOUS_DISABLE_DOCKER</code> instead of pinning a choice.
            </div>
          </div>
        </label>
        <div className="text-xs text-ink-500">
          {value === null ? (
            <span className="text-ink-400">Not set — using server default</span>
          ) : (
            <>
              Will save as:{' '}
              <span className="font-mono text-ink-700">{value ? 'Docker' : 'Native'}</span>
            </>
          )}
          {value !== null && (
            <button
              type="button"
              onClick={() => onChange(null)}
              className="ml-3 text-xs text-accent-600 hover:underline"
            >
              Reset to server default
            </button>
          )}
        </div>
      </div>
    </SectionCard>
  );
}

function snapshot(ctx: {
  credentials: CredentialMap;
  activeBackend: Record<AgentFamily, BackendChoice>;
  useDocker: boolean | null;
}): Draft {
  return {
    credentials: {
      claude: { ...ctx.credentials.claude },
      codex: { ...ctx.credentials.codex },
    },
    activeBackend: { ...ctx.activeBackend },
    useDocker: ctx.useDocker,
  };
}

function diffCount(a: Draft, b: Draft): number {
  let n = 0;
  for (const f of ['claude', 'codex'] as AgentFamily[]) {
    if (a.credentials[f].api !== b.credentials[f].api) n++;
    if (a.credentials[f].miromind !== b.credentials[f].miromind) n++;
    if (a.activeBackend[f] !== b.activeBackend[f]) n++;
  }
  if (a.useDocker !== b.useDocker) n++;
  return n;
}

export default function Settings() {
  const { credentials, activeBackend, useDocker, setKey, setActiveBackend, setUseDocker } =
    useApiKey();

  const committed = useMemo<Draft>(
    () => snapshot({ credentials, activeBackend, useDocker }),
    [credentials, activeBackend, useDocker],
  );
  const [draft, setDraft] = useState<Draft>(committed);
  const [saved, setSaved] = useState(false);

  // When committed state changes (another tab saved, or we just committed),
  // realign the draft only if there are no in-flight local edits — otherwise
  // we'd clobber the user's typing.
  const dirtyCount = diffCount(draft, committed);
  useEffect(() => {
    if (dirtyCount === 0) setDraft(committed);
  }, [committed, dirtyCount]);

  const onSave = () => {
    for (const f of ['claude', 'codex'] as AgentFamily[]) {
      for (const slot of ['api', 'miromind'] as Slot[]) {
        if (draft.credentials[f][slot] !== committed.credentials[f][slot]) {
          setKey(f, slot, draft.credentials[f][slot]);
        }
      }
      if (draft.activeBackend[f] !== committed.activeBackend[f]) {
        setActiveBackend(f, draft.activeBackend[f]);
      }
    }
    if (draft.useDocker !== committed.useDocker) {
      setUseDocker(draft.useDocker);
    }
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  };

  const onRevert = () => setDraft(committed);

  return (
    <>
      <PageHeader
        title="Settings"
        subtitle="Configure credentials; every experiment run uses these values at run time."
        symbol="λ"
      />

      <div className="max-w-2xl space-y-6">
        <p className="text-sm text-ink-500">
          Every experiment — new, restart, or resume — reads these values at run time.
          Changes take effect on the next click without touching the experiments themselves.
        </p>

        <FamilySection family="claude" draft={draft} setDraft={setDraft} />
        <FamilySection family="codex" draft={draft} setDraft={setDraft} />
        <RuntimeSection
          value={draft.useDocker}
          onChange={(v) => setDraft({ ...draft, useDocker: v })}
        />

        <div className="sticky bottom-0 -mx-2 border-t border-slate-200 bg-white/95 px-2 py-3 backdrop-blur">
          <div className="flex items-center gap-3">
            <button
              className={btnPrimary}
              disabled={dirtyCount === 0}
              onClick={onSave}
            >
              {saved ? <Check size={14} /> : <Save size={14} />}
              {saved ? 'Saved' : 'Save changes'}
            </button>
            <button
              className={btnSecondary}
              disabled={dirtyCount === 0}
              onClick={onRevert}
            >
              <RotateCcw size={14} />
              Revert
            </button>
            <span className="text-xs text-ink-500">
              {dirtyCount === 0
                ? 'All saved'
                : `${dirtyCount} unsaved change${dirtyCount === 1 ? '' : 's'}`}
            </span>
          </div>
        </div>
      </div>
    </>
  );
}
