export type Page<T> = { items: T[]; total: number; page: number; page_size: number };

export type RepoSide = {
  owner: string;
  name: string;
  url: string;
  default_branch?: string | null;
  verified?: boolean | null;
};

export type Repo = {
  id: number;
  upstream: RepoSide;
  fork: RepoSide;
  language?: string | null;
  stars?: number | null;
  health_score?: number | null;
  health_verdict?: string | null;
  current_phase: string;
  paused: boolean;
  pause_reason?: string | null;
  open_pr_count?: number | null;
  merged_pr_count?: number | null;
  merge_rate?: number | null;
  created_at: string;
  last_action_at?: string | null;
};

export type Issue = {
  id: number;
  repo_id: number;
  github_number: number;
  title?: string | null;
  labels: string[];
  github_state?: string | null;
  github_url?: string | null;
  score?: number | null;
  eligibility_verdict?: string | null;
  filter_reason?: string | null;
  reproducibility_confidence?: number | null;
  status: string;
  detected_at?: string | null;
};

export type PR = {
  id: number;
  repo_id: number;
  type?: string | null;
  issue_id?: number | null;
  no_brainer_id?: number | null;
  upstream_pr_number?: number | null;
  upstream_url?: string | null;
  title?: string | null;
  fork_branch_name?: string | null;
  files_changed_count?: number | null;
  loc_added?: number | null;
  loc_removed?: number | null;
  status?: string | null;
  opened_at?: string | null;
  buffer_until?: string | null;
  grace_until?: string | null;
  latest_traction?: {
    traction_score: number;
    verdict?: string | null;
  } | null;
};

export type Run = {
  id: number;
  kind: string;
  repo_id: number;
  issue_id?: number | null;
  no_brainer_id?: number | null;
  stage?: string | null;
  status: string;
  started_at?: string | null;
  finished_at?: string | null;
};

export type LogEvent = {
  id: number;
  ts?: string | null;
  level?: string | null;
  stage?: string | null;
  message?: string | null;
};

export type NoBrainer = {
  id: number;
  repo_id: number;
  type?: string | null;
  file?: string | null;
  summary?: string | null;
  proposed_change?: string | null;
  confidence?: number | null;
  status: string;
  pr_id?: number | null;
  detected_at?: string | null;
};
