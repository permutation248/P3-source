import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

export type AgentFamily = 'claude' | 'codex';
export type Backend = 'api' | 'miromind' | 'subscription';
/** 'default' = send no X-Backend / no X-API-Key; server uses its baseline
 *  env vars or mounted OAuth. UI sentinel only — not a real backend value. */
export type BackendChoice = Backend | 'default';

/** Human-readable labels for every backend choice. Single source of truth
 *  so Settings / NewExperiment / ExperimentDetail stay in sync. */
export const BACKEND_LABELS: Record<BackendChoice, string> = {
  default: 'Default (server environment)',
  api: 'Official API Key',
  miromind: 'MiroMind Gateway',
  subscription: 'Subscription (server OAuth)',
};

/** Mirror of the server's ``_resolve_agent_type`` precedence:
 *    1. model name matches OpenAI family (gpt-* / *codex*)
 *    2. explicit agent_type == "codex"
 *    3. otherwise → claude
 *  Front and back must agree; a drift here mis-routes the credential key
 *  into the wrong family's slot. */
export function familyForExperiment(
  agentType: string | null | undefined,
  model: string | null | undefined,
): AgentFamily {
  const m = (model ?? '').trim().toLowerCase();
  if (m.startsWith('gpt-') || m.includes('codex')) return 'codex';
  if ((agentType ?? '').trim().toLowerCase() === 'codex') return 'codex';
  return 'claude';
}

export interface RequestAuth {
  backend: BackendChoice | null;
  apiKey?: string;
  /** null/undefined = omit X-Use-Docker header (server uses its env default). */
  useDocker?: boolean | null;
}

/** Per-(family, backend) credential store. Subscription has no key — its
 *  availability is determined by whether the server has OAuth creds mounted. */
export type CredentialMap = {
  [F in AgentFamily]: {
    api: string;
    miromind: string;
  };
};

interface CredentialsContextType {
  credentials: CredentialMap;
  setKey: (family: AgentFamily, backend: 'api' | 'miromind', value: string) => void;
  clearKey: (family: AgentFamily, backend: 'api' | 'miromind') => void;
  /** True iff server has OAuth credentials mounted for this family. */
  subscriptionAvailable: Record<AgentFamily, boolean>;
  /** True once the /api/config/oauth-status probe has resolved (ok or error). */
  subscriptionProbed: boolean;
  /** List of backends selectable for *family* (excluding 'default', which
   *  is always available). */
  availableBackends: (family: AgentFamily) => Backend[];
  /** Lookup the stored key for a (family, backend) pair ("" for subscription). */
  keyFor: (family: AgentFamily, backend: Backend) => string;
  /** Active backend chosen in Settings for *family*. Every run (new or
   *  rerun) reads this — experiments don't carry their own backend. */
  activeBackend: Record<AgentFamily, BackendChoice>;
  setActiveBackend: (family: AgentFamily, choice: BackendChoice) => void;
  /** Tri-state Docker toggle: ``null`` ⇒ follow server env default
   *  (``ANONYMOUS_DISABLE_DOCKER``); ``true``/``false`` ⇒ explicit override. */
  useDocker: boolean | null;
  setUseDocker: (v: boolean | null) => void;
  /** Build the HTTP auth + runtime payload for *family* from Settings. */
  authForFamily: (family: AgentFamily) => RequestAuth;
  /** True if any credential is configured anywhere — used by the sidebar
   *  status badge as a "is this browser set up at all" indicator. */
  hasApiKey: boolean;
}

const CredentialsContext = createContext<CredentialsContextType | null>(null);

const STORAGE_PREFIX = 'anonymous_cred_';

function storageKey(family: AgentFamily, backend: 'api' | 'miromind'): string {
  return `${STORAGE_PREFIX}${family}_${backend}`;
}

function activeBackendStorageKey(family: AgentFamily): string {
  return `${STORAGE_PREFIX}${family}_active_backend`;
}

function readActiveBackend(family: AgentFamily): BackendChoice {
  const v = localStorage.getItem(activeBackendStorageKey(family));
  if (v === 'api' || v === 'miromind' || v === 'subscription' || v === 'default') return v;
  return 'default';
}

const USE_DOCKER_STORAGE_KEY = `${STORAGE_PREFIX}use_docker`;

function readUseDocker(): boolean | null {
  const v = localStorage.getItem(USE_DOCKER_STORAGE_KEY);
  if (v === '1') return true;
  if (v === '0') return false;
  return null;
}

function loadCredentials(): CredentialMap {
  return {
    claude: {
      api: localStorage.getItem(storageKey('claude', 'api')) ?? '',
      miromind: localStorage.getItem(storageKey('claude', 'miromind')) ?? '',
    },
    codex: {
      api: localStorage.getItem(storageKey('codex', 'api')) ?? '',
      miromind: localStorage.getItem(storageKey('codex', 'miromind')) ?? '',
    },
  };
}

export function ApiKeyProvider({ children }: { children: ReactNode }) {
  const [credentials, setCredentials] = useState<CredentialMap>(() => loadCredentials());
  const [subscriptionAvailable, setSubscriptionAvailable] = useState<Record<AgentFamily, boolean>>({
    claude: false,
    codex: false,
  });
  const [subscriptionProbed, setSubscriptionProbed] = useState(false);
  const [activeBackend, setActiveBackendState] = useState<Record<AgentFamily, BackendChoice>>(() => ({
    claude: readActiveBackend('claude'),
    codex: readActiveBackend('codex'),
  }));
  const [useDocker, setUseDockerState] = useState<boolean | null>(() => readUseDocker());

  // Probe server for mounted OAuth credentials.
  useEffect(() => {
    fetch('/api/config/oauth-status')
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && typeof data === 'object') {
          setSubscriptionAvailable({
            claude: Boolean(data.claude),
            codex: Boolean(data.codex),
          });
        }
      })
      .catch(() => {
        /* noop */
      })
      .finally(() => setSubscriptionProbed(true));
  }, []);

  const setKey = useCallback(
    (family: AgentFamily, backend: 'api' | 'miromind', value: string) => {
      setCredentials((prev) => {
        if (prev[family][backend] === value) return prev;
        const slot = storageKey(family, backend);
        if (value) localStorage.setItem(slot, value);
        else localStorage.removeItem(slot);
        return {
          ...prev,
          [family]: { ...prev[family], [backend]: value },
        };
      });
    },
    [],
  );

  const clearKey = useCallback(
    (family: AgentFamily, backend: 'api' | 'miromind') => setKey(family, backend, ''),
    [setKey],
  );

  const keyFor = useCallback(
    (family: AgentFamily, backend: Backend): string => {
      if (backend === 'subscription') return '';
      return credentials[family][backend];
    },
    [credentials],
  );

  const availableBackends = useCallback(
    (family: AgentFamily): Backend[] => {
      const out: Backend[] = ['api', 'miromind'];
      if (subscriptionAvailable[family]) out.push('subscription');
      return out;
    },
    [subscriptionAvailable],
  );

  const setActiveBackend = useCallback(
    (family: AgentFamily, choice: BackendChoice) => {
      setActiveBackendState((prev) => {
        if (prev[family] === choice) return prev;
        localStorage.setItem(activeBackendStorageKey(family), choice);
        return { ...prev, [family]: choice };
      });
    },
    [],
  );

  const setUseDocker = useCallback((v: boolean | null) => {
    setUseDockerState((prev) => {
      if (prev === v) return prev;
      if (v === null) localStorage.removeItem(USE_DOCKER_STORAGE_KEY);
      else localStorage.setItem(USE_DOCKER_STORAGE_KEY, v ? '1' : '0');
      return v;
    });
  }, []);

  const authForFamily = useCallback(
    (family: AgentFamily): RequestAuth => {
      // Single source of truth for every run (create / restart / resume):
      // the active backend + key for this family, plus the global
      // Docker toggle. Changing Settings immediately changes future runs.
      const choice = activeBackend[family];
      const base: RequestAuth =
        choice === 'default'
          ? { backend: 'default' }
          : choice === 'subscription'
            ? { backend: 'subscription' }
            : { backend: choice, apiKey: keyFor(family, choice) || undefined };
      return { ...base, useDocker };
    },
    [activeBackend, keyFor, useDocker],
  );

  const hasApiKey = useMemo(
    () =>
      Boolean(
        credentials.claude.api ||
          credentials.claude.miromind ||
          credentials.codex.api ||
          credentials.codex.miromind ||
          subscriptionAvailable.claude ||
          subscriptionAvailable.codex,
      ),
    [credentials, subscriptionAvailable],
  );

  const value = useMemo<CredentialsContextType>(
    () => ({
      credentials,
      setKey,
      clearKey,
      subscriptionAvailable,
      subscriptionProbed,
      availableBackends,
      keyFor,
      activeBackend,
      setActiveBackend,
      useDocker,
      setUseDocker,
      authForFamily,
      hasApiKey,
    }),
    [
      credentials,
      setKey,
      clearKey,
      subscriptionAvailable,
      subscriptionProbed,
      availableBackends,
      keyFor,
      activeBackend,
      setActiveBackend,
      useDocker,
      setUseDocker,
      authForFamily,
      hasApiKey,
    ],
  );

  return <CredentialsContext.Provider value={value}>{children}</CredentialsContext.Provider>;
}

export function useApiKey(): CredentialsContextType {
  const ctx = useContext(CredentialsContext);
  if (!ctx) throw new Error('useApiKey must be used within ApiKeyProvider');
  return ctx;
}
