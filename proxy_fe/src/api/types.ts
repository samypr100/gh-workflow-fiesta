// Mirrors contract/src/bench_contract/. Phase 2 replaces this with types
// generated from the backend's /openapi.json; tests/fixtures.test.ts is what
// catches drift until then.

export type OperatingSystem = 'linux' | 'macos' | 'windows';
export type Variant = 'default' | 'freethreaded';
export type WorkloadKind = 'cpu_bound' | 'io_bound' | 'mixed';
export type ExecutionModel =
  | 'sequential'
  | 'threading'
  | 'asyncio'
  | 'multiprocessing'
  | 'subinterpreters';
export type RunStatus = 'ok' | 'error' | 'timeout';
export type CpuCountSource = 'reported' | 'override';
export type ApiRunPhase = 'pending' | 'running' | 'complete' | 'failed';

export interface WorkloadParams {
  readonly workers: number;
  readonly iterations: number;
  readonly repeats: number;
}

export interface LegKey {
  readonly leg_id: string;
  readonly os: OperatingSystem;
  readonly arch: string;
  readonly python_key: string;
  readonly variant: Variant;
  readonly workload: WorkloadKind;
  readonly execution_model: ExecutionModel;
  readonly params: WorkloadParams;
  readonly cpu_count_override: number | null;
}

export interface ScalarStats {
  readonly median: number;
  readonly minimum: number;
  readonly maximum: number;
}

export interface Scalars {
  readonly wall_time_s: ScalarStats;
  readonly cpu_user_s: ScalarStats;
  readonly cpu_sys_s: ScalarStats;
  readonly parallelism_factor: ScalarStats;
  readonly peak_rss_bytes: ScalarStats;
  readonly throughput_ops_s: ScalarStats | null;
  readonly repeats_completed: number;
}

export interface Environment {
  readonly runner_os: OperatingSystem;
  readonly runner_arch: string;
  readonly cpu_model: string;
  readonly logical_cores: number;
  readonly physical_cores: number | null;
  readonly total_memory_bytes: number;
  readonly python_version: string;
  readonly python_implementation: string;
  readonly gil_enabled: boolean;
  readonly cpu_count_effective: number;
  readonly cpu_count_source: CpuCountSource;
  readonly resolved_interpreter_key: string;
}

export interface TimelinePoint {
  readonly t_s: number;
  readonly cpu_percent: number;
  readonly num_threads: number;
  readonly rss_bytes: number;
}

export interface Phase {
  readonly name: string;
  readonly duration_s: number;
}

export interface LegError {
  readonly kind: string;
  readonly message: string;
}

export interface RunResult {
  readonly leg: LegKey;
  readonly status: RunStatus;
  readonly environment: Environment | null;
  readonly scalars: Scalars | null;
  readonly timeline: readonly TimelinePoint[];
  readonly phases: readonly Phase[];
  readonly error: LegError | null;
}

export interface CatalogItem {
  readonly workload: WorkloadKind;
  readonly execution_model: ExecutionModel;
  readonly minimum_python_minor: number;
  readonly title: string;
  readonly explainer: string;
  readonly expectation: string;
}

export interface CatalogResponse {
  readonly items: readonly CatalogItem[];
  readonly default_workers: number;
  readonly default_iterations: number;
  readonly max_workers: number;
  readonly max_iterations: number;
}

export interface InterpreterOption {
  readonly python_key: string;
  readonly version: string;
  readonly python_minor: number;
  readonly os: OperatingSystem;
  readonly arch: string;
  readonly variant: Variant;
  readonly gil_enabled: boolean;
}

export interface InterpretersResponse {
  readonly interpreters: readonly InterpreterOption[];
}

export interface RunnerInfo {
  readonly os: OperatingSystem;
  readonly arch: string;
  readonly logical_cores: number;
}

export interface RunnersResponse {
  readonly runners: readonly RunnerInfo[];
}

export interface SelectionRequest {
  readonly os: OperatingSystem;
  readonly python_key: string;
  readonly workload: WorkloadKind;
  readonly execution_model: ExecutionModel;
  readonly workers: number;
  readonly iterations: number;
}

export interface CreateRunResponse {
  readonly run_token: string;
  readonly leg_count: number;
}

export interface RunStatusResponse {
  readonly phase: ApiRunPhase;
  readonly expected_legs: number;
  readonly results: readonly RunResult[];
  readonly detail: string | null;
}
