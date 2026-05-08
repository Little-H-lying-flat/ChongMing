"use client";

import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Brain, Layers, Sparkles, Loader2, FileText, AlertCircle, UploadCloud } from "lucide-react";
import { toast } from "sonner";
import { useRouter } from "next/navigation";
import { visualUiService } from "@/services/visualUiService";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
    Accordion,
    AccordionContent,
    AccordionItem,
    AccordionTrigger,
} from "@/components/ui/accordion";
import { Skeleton } from "@/components/ui/skeleton";

// --- Types ---
interface DesignRequest {
    project_id: string;
    requirement_text: string;
    context?: string;
    target_type: "API" | "UI" | "MIXED";
}

interface GeneratedScenario {
    scenario_id: string;
    description: string;
    priority: "Critical" | "High" | "Normal";
    name?: string;
    required_variables?: string[];
    steps: Array<{
        step_type: "API" | "UI";
        description: string;
        action?: string;
        target?: string | Record<string, unknown>;
        value?: string;
        method?: string;
        url?: string;
        url_path?: string;
        body?: unknown;
        input_data?: Record<string, unknown>;
        expected_result?: string;
        expected_status_code?: number;
        json_assertions?: Record<string, unknown>;
        extract?: Record<string, string>;
        payload?: Record<string, unknown>;
    } | string>; // Backwards compatibility
}

interface AnalyzeTaskResponse {
    task_id: string;
    status: "pending" | "running" | "completed" | "failed" | "cancelled";
    stage: string;
    progress: number;
    status_url: string;
    result_url: string;
    created_at: string;
    updated_at: string;
    error?: string | null;
}

interface AnalyzeTaskResultResponse {
    task_id: string;
    status: "completed" | "failed" | "pending" | "running";
    scenarios: GeneratedScenario[];
    error?: string | null;
}

interface DefaultEnvironmentResponse {
    id: string;
    name: string;
    variables: Record<string, { value: string; encrypted?: boolean; description?: string }>;
}

type EnvironmentReadinessState =
    | { status: "idle"; env: null; error?: undefined }
    | { status: "loading"; env: null; error?: undefined }
    | { status: "ready"; env: DefaultEnvironmentResponse; error?: undefined }
    | { status: "missing"; env: null; error?: undefined }
    | { status: "error"; env: null; error: string };

interface ScenarioRunReadiness {
    status: "ready" | "checking" | "missing_env" | "missing_variables" | "error";
    label: string;
    missingVariables: string[];
}

const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));

const VARIABLE_REF_PATTERN = /\$\{([^}]+)\}|\{\{([^}]+)\}\}/g;

const collectRequiredVariables = (value: unknown, bucket: Set<string>) => {
    if (typeof value === "string") {
        for (const match of value.matchAll(VARIABLE_REF_PATTERN)) {
            const variableName = (match[1] || match[2] || "").trim();
            if (variableName) bucket.add(variableName);
        }
        return;
    }

    if (Array.isArray(value)) {
        value.forEach((item) => collectRequiredVariables(item, bucket));
        return;
    }

    if (value && typeof value === "object") {
        Object.values(value as Record<string, unknown>).forEach((item) => collectRequiredVariables(item, bucket));
    }
};

const getScenarioRequiredVariables = (scenario: GeneratedScenario): string[] => {
    const required = new Set<string>(scenario.required_variables || []);
    collectRequiredVariables(scenario.steps, required);
    return Array.from(required).sort();
};

const getScenarioRunReadiness = (
    scenario: GeneratedScenario,
    envState: EnvironmentReadinessState,
): ScenarioRunReadiness => {
    const requiredVariables = getScenarioRequiredVariables(scenario);
    if (requiredVariables.length === 0) {
        return { status: "ready", label: "可运行", missingVariables: [] };
    }

    if (envState.status === "idle" || envState.status === "loading") {
        return { status: "checking", label: "检查环境中", missingVariables: [] };
    }

    if (envState.status === "missing") {
        return { status: "missing_env", label: "未配置默认环境", missingVariables: requiredVariables };
    }

    if (envState.status === "error") {
        return { status: "error", label: "环境检查失败", missingVariables: [] };
    }

    const availableVariables = new Set<string>(Object.keys(envState.env.variables || {}));
    availableVariables.add("base_url");
    const missingVariables = requiredVariables.filter((variableName) => !availableVariables.has(variableName));
    if (missingVariables.length > 0) {
        return {
            status: "missing_variables",
            label: `缺变量: ${missingVariables.join(", ")}`,
            missingVariables,
        };
    }

    return { status: "ready", label: "可运行", missingVariables: [] };
};

// --- API ---
const analyzeDesignAsync = async (
    data: DesignRequest,
    onTaskUpdate: (task: AnalyzeTaskResponse) => void,
): Promise<GeneratedScenario[]> => {
    const createRes = await fetch("/api/v1/design/analyze/async", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });

    if (!createRes.ok) {
        const errorText = await createRes.text();
        console.error("Analysis Task Create Failed:", createRes.status, createRes.statusText, errorText);
        throw new Error(`Failed to create analyze task: ${createRes.status} ${createRes.statusText} - ${errorText.substring(0, 100)}`);
    }

    const createdTask: AnalyzeTaskResponse = await createRes.json();
    onTaskUpdate(createdTask);

    const startedAt = Date.now();
    const timeoutMs = 5 * 60 * 1000;

    while (Date.now() - startedAt < timeoutMs) {
        await sleep(1500);

        const statusRes = await fetch(createdTask.status_url, { cache: "no-store" });
        if (!statusRes.ok) {
            const errorText = await statusRes.text();
            throw new Error(`Failed to get analyze task status: ${statusRes.status} ${statusRes.statusText} - ${errorText.substring(0, 100)}`);
        }

        const taskStatus: AnalyzeTaskResponse = await statusRes.json();
        onTaskUpdate(taskStatus);

        if (taskStatus.status === "failed" || taskStatus.status === "cancelled") {
            throw new Error(taskStatus.error || "Analyze task failed");
        }

        if (taskStatus.status === "completed") {
            const resultRes = await fetch(createdTask.result_url, { cache: "no-store" });
            const resultText = await resultRes.text();

            if (!resultRes.ok) {
                throw new Error(`Failed to fetch analyze result: ${resultRes.status} ${resultRes.statusText} - ${resultText.substring(0, 100)}`);
            }

            const resultData: AnalyzeTaskResultResponse = JSON.parse(resultText);
            return resultData.scenarios || [];
        }
    }

    throw new Error("Analyze task timed out while polling");
};

export default function NeuralDesignPage() {
    const router = useRouter();
    const [projectId, setProjectId] = useState("proj_001");
    const [requirement, setRequirement] = useState("");
    const [targetType, setTargetType] = useState<"API" | "UI" | "MIXED">("MIXED");
    const [uploading, setUploading] = useState(false);
    const [analysisTask, setAnalysisTask] = useState<AnalyzeTaskResponse | null>(null);
    const [environmentState, setEnvironmentState] = useState<EnvironmentReadinessState>({
        status: "idle",
        env: null,
    });

    // File Upload Handler
    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        setUploading(true);
        const formData = new FormData();
        formData.append("file", file);

        try {
            const res = await fetch("/api/v1/design/upload", {
                method: "POST",
                body: formData,
            });

            if (!res.ok) {
                const text = await res.text();
                throw new Error("解析失败: " + text);
            }

            const data = await res.json();

            // Append or overwrite? Usually users want to overwrite with the document but maybe keep context. Lets overwrite.
            setRequirement(data.extracted_text);

            // Auto-switch target type if swagger
            const extractedText = String(data.extracted_text || "").toLowerCase();
            if (data.file_type === "json" && (extractedText.includes("openapi") || extractedText.includes("paths"))) {
                setTargetType("API");
            }

            toast.success("文档解析成功 (Parsed Successfully)", {
                description: `从 ${data.filename} 提取了内容。`
            });
        } catch (error) {
            toast.error("文档解析失败 (Parse Failed)", {
                description: String(error)
            });
        } finally {
            setUploading(false);
            e.target.value = ''; // Reset file input
        }
    };

    // React Query Mutation
    const { mutate, data: scenarios, isPending, isError, error } = useMutation({
        mutationFn: (data: DesignRequest) => analyzeDesignAsync(data, setAnalysisTask),
        onError: (err) => {
            console.error(err);
            // Optional: integration with toast if available
            // toast.error("Failed to generate scenarios");
        },
    });

    const handleGenerate = () => {
        if (!requirement.trim()) return;
        setAnalysisTask(null);
        setEnvironmentState({ status: "idle", env: null });
        mutate({
            project_id: projectId,
            requirement_text: requirement,
            context: "", // Optional context
            target_type: targetType
        });
    };

    useEffect(() => {
        if (!scenarios || scenarios.length === 0) {
            setEnvironmentState({ status: "idle", env: null });
            return;
        }

        const needsEnvironment = scenarios.some((scenario) => getScenarioRequiredVariables(scenario).length > 0);
        if (!needsEnvironment) {
            setEnvironmentState({ status: "idle", env: null });
            return;
        }

        let cancelled = false;
        setEnvironmentState({ status: "loading", env: null });

        const loadDefaultEnvironment = async () => {
            try {
                const res = await fetch("/api/v1/environments/default", { cache: "no-store" });
                if (cancelled) return;

                if (res.ok) {
                    const envData: DefaultEnvironmentResponse = await res.json();
                    if (!cancelled) {
                        setEnvironmentState({ status: "ready", env: envData });
                    }
                    return;
                }

                if (res.status === 404) {
                    setEnvironmentState({ status: "missing", env: null });
                    return;
                }

                const errorText = await res.text();
                setEnvironmentState({
                    status: "error",
                    env: null,
                    error: errorText.substring(0, 120) || "Failed to load default environment",
                });
            } catch (error) {
                if (!cancelled) {
                    setEnvironmentState({
                        status: "error",
                        env: null,
                        error: String(error),
                    });
                }
            }
        };

        void loadDefaultEnvironment();
        return () => {
            cancelled = true;
        };
    }, [scenarios]);

    const getPriorityColor = (p?: string) => {
        if (!p) return "bg-slate-500 hover:bg-slate-600 border-none";
        switch (p.toUpperCase()) {
            case "P0": return "bg-red-500 hover:bg-red-600 border-none";
            case "P1": return "bg-orange-500 hover:bg-orange-600 border-none";
            case "P2": return "bg-yellow-500 hover:bg-yellow-600 border-none text-black";
            default: return "bg-slate-500 hover:bg-slate-600 border-none";
        }
    };

    return (
        <div className="flex bg-slate-950 text-slate-100">

            {/* --- Left Pane: Input (40%) --- */}
            <div className="w-[40%] flex flex-col p-6 border-r border-slate-800 space-y-6 h-[calc(100vh-64px)] overflow-hidden">
                <div>
                    <h2 className="text-2xl font-bold tracking-tight bg-gradient-to-r from-blue-400 to-cyan-300 bg-clip-text text-transparent flex items-center gap-2">
                        <Brain className="w-6 h-6 text-blue-500" />
                        需求解析 (Neural Design)
                    </h2>
                    <p className="text-slate-400 text-sm mt-1">
                        将需求转换为测试场景 (Transform requirements into test scenarios via LLM.)
                    </p>
                </div>

                <div className="space-y-4 flex-1 flex flex-col">
                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-slate-300">项目ID (Project ID)</label>
                            <Input
                                value={projectId}
                                onChange={(e) => setProjectId(e.target.value)}
                                className="bg-slate-900 border-slate-700 focus:border-blue-500 font-mono"
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-slate-300">目标类型 (Target Type)</label>
                            <div className="flex bg-slate-900 p-1 rounded-md border border-slate-700">
                                {(["API", "UI", "MIXED"] as const).map((type) => (
                                    <button
                                        key={type}
                                        onClick={() => setTargetType(type)}
                                        className={`flex-1 text-xs font-medium py-1.5 rounded-sm transition-all ${targetType === type
                                            ? "bg-blue-600 text-white shadow-sm"
                                            : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
                                            }`}
                                    >
                                        {type}
                                    </button>
                                ))}
                            </div>
                        </div>
                    </div>

                    <div className="space-y-2 flex-1 flex flex-col">
                        <div className="flex justify-between items-center text-sm font-medium text-slate-300">
                            <label>需求描述 (Requirement Description (PRD))</label>

                            <Button
                                variant="outline"
                                size="sm"
                                className="h-7 text-xs border-indigo-500/30 bg-indigo-500/10 text-indigo-400 hover:text-indigo-300 hover:bg-indigo-500/20"
                                onClick={() => document.getElementById("prd-upload")?.click()}
                                disabled={uploading || isPending}
                            >
                                {uploading ? <Loader2 className="w-3 h-3 mr-1.5 animate-spin" /> : <UploadCloud className="w-3 h-3 mr-1.5" />}
                                上传文档 (.md, .pdf, .json)
                            </Button>
                            <input
                                type="file"
                                id="prd-upload"
                                className="hidden"
                                accept=".md,.pdf,.json,.txt"
                                onChange={handleFileUpload}
                            />
                        </div>
                        <Textarea
                            value={requirement}
                            onChange={(e) => setRequirement(e.target.value)}
                            placeholder="在此粘贴需求文档、API文档或描述功能逻辑... (Paste your PRD content, API docs, or describe the feature logic here...)"
                            className="flex-1 bg-slate-900 border-slate-700 focus:border-blue-500 resize-none font-mono text-sm leading-relaxed p-4"
                        />
                    </div>
                </div>

                <Button
                    onClick={handleGenerate}
                    disabled={isPending || !requirement.trim()}
                    size="lg"
                    className="w-full bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-700 hover:to-cyan-700 text-white shadow-lg shadow-blue-900/20 transition-all duration-300"
                >
                    {isPending ? (
                        <>
                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                            解析中... (Analyzing...)
                        </>
                    ) : (
                        <>
                            <Sparkles className="w-4 h-4 mr-2 group-hover:animate-pulse" />
                            生成测试场景 (Generate Test Scenarios)
                        </>
                    )}
                </Button>
            </div>

            {/* --- Right Pane: Output (60%) --- */}
            <div className="w-[60%] p-8 bg-slate-950/50 h-[calc(100vh-64px)] overflow-hidden flex flex-col">
                {/* State: Empty */}
                {!scenarios && !isPending && !isError && (
                    <div className="flex-1 flex flex-col items-center justify-center text-slate-500 space-y-4 opacity-70">
                        <div className="w-24 h-24 rounded-full bg-slate-900 border border-slate-800 flex items-center justify-center">
                            <FileText className="w-10 h-10" />
                        </div>
                        <p className="text-lg">在左侧粘贴需求以唤醒AI大脑... (Paste requirements on the left to wake up the AI brain...)</p>
                    </div>
                )}

                {/* State: Loading (Skeleton) */}
                {isPending && (
                    <div className="space-y-4 animate-in fade-in duration-500">
                        <div className="flex items-center gap-2 text-blue-400 mb-6">
                            <Loader2 className="w-4 h-4 animate-spin" />
                            {analysisTask && (
                                <span className="text-sm font-mono">
                                    {`任务 ${analysisTask.task_id} | ${analysisTask.stage} | ${analysisTask.progress}%`}
                                </span>
                            )}
                            <span className="text-sm font-mono">深度思考中... (Deep thinking in progress...)</span>
                        </div>
                        {[1, 2, 3].map((i) => (
                            <Card key={i} className="bg-slate-900 border-slate-800">
                                <CardHeader className="pb-2">
                                    <Skeleton className="h-6 w-3/4 bg-slate-800" />
                                </CardHeader>
                                <CardContent>
                                    <Skeleton className="h-4 w-full bg-slate-800 mb-2" />
                                    <Skeleton className="h-4 w-5/6 bg-slate-800" />
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                )}

                {/* State: Error */}
                {isError && (
                    <div className="flex-1 flex items-center justify-center text-red-400">
                        <div className="flex flex-col items-center space-y-2">
                            <AlertCircle className="w-12 h-12" />
                            <p>生成场景失败，请重试。 (Failed to generate scenarios. Please try again.)</p>
                            <p className="text-xs text-slate-600">{error.message}</p>
                        </div>
                    </div>
                )}

                {/* State: Success (Results) */}
                {scenarios && !isPending && (
                    <ScrollArea className="flex-1 pr-4">
                        <div className="space-y-4 animate-in slide-in-from-bottom-4 duration-500">
                            <div className="flex justify-between items-center mb-4">
                                <div>
                                    <h3 className="text-lg font-semibold text-slate-200">
                                        生成的场景 (Generated Scenarios)
                                        <span className="ml-2 text-xs bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded-full">
                                            {scenarios.length}
                                        </span>
                                    </h3>
                                    {environmentState.status === "loading" && (
                                        <p className="mt-1 text-xs text-slate-400">正在检查默认环境变量...</p>
                                    )}
                                    {environmentState.status === "ready" && (
                                        <p className="mt-1 text-xs text-emerald-400">
                                            默认环境: {environmentState.env.name}
                                        </p>
                                    )}
                                    {environmentState.status === "missing" && (
                                        <p className="mt-1 text-xs text-amber-400">
                                            当前未配置默认环境。依赖变量的场景将无法直接运行。
                                        </p>
                                    )}
                                    {environmentState.status === "error" && (
                                        <p className="mt-1 text-xs text-rose-400">
                                            默认环境检查失败: {environmentState.error}
                                        </p>
                                    )}
                                </div>
                            </div>

                            <Accordion type="single" collapsible className="w-full space-y-4">
                                {scenarios.map((scenario) => (
                                    <AccordionItem
                                        key={scenario.scenario_id}
                                        value={scenario.scenario_id}
                                        className="bg-slate-900 border border-slate-800 rounded-lg px-2 data-[state=open]:border-blue-500/50 transition-all"
                                    >
                                        {(() => {
                                            const requiredVariables = getScenarioRequiredVariables(scenario);
                                            const runReadiness = getScenarioRunReadiness(scenario, environmentState);
                                            return (
                                        <div className="flex items-center w-full bg-slate-900 border border-slate-800 rounded-lg px-2 hover:bg-slate-900/50 transition-all">
                                            <AccordionTrigger className="px-4 py-3 flex-1 hover:no-underline">
                                                <div className="flex items-center gap-3 w-full text-left">
                                                    <div className="p-2 rounded-md bg-blue-500/10 text-blue-400">
                                                        <Layers className="w-4 h-4" />
                                                    </div>
                                                    <div className="flex-1">
                                                        <div className="flex items-center gap-2">
                                                            <span className="font-semibold text-slate-200">{scenario.name || "场景 (Scenario)"}</span>
                                                            <Badge className={getPriorityColor(scenario.priority)}>
                                                                {scenario.priority || "普通 (Normal)"}
                                                            </Badge>
                                                        </div>
                                                        <p className="text-xs text-slate-500 mt-0.5 line-clamp-1 text-left">
                                                            {scenario.description}
                                                        </p>
                                                        {requiredVariables.length > 0 && (
                                                            <div className="mt-1 flex flex-wrap gap-1">
                                                                {requiredVariables.map((variableName) => (
                                                                    <span
                                                                        key={variableName}
                                                                        className="inline-flex items-center rounded border border-rose-500/20 bg-rose-500/10 px-2 py-0.5 text-[10px] text-rose-300"
                                                                    >
                                                                        {variableName}
                                                                    </span>
                                                                ))}
                                                            </div>
                                                        )}
                                                        <div className="mt-2">
                                                            <span
                                                                className={`inline-flex items-center rounded border px-2 py-0.5 text-[10px] ${
                                                                    runReadiness.status === "ready"
                                                                        ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-300"
                                                                        : runReadiness.status === "checking"
                                                                            ? "border-blue-500/20 bg-blue-500/10 text-blue-300"
                                                                            : "border-amber-500/20 bg-amber-500/10 text-amber-300"
                                                                }`}
                                                            >
                                                                {runReadiness.label}
                                                            </span>
                                                        </div>
                                                    </div>
                                                </div>
                                            </AccordionTrigger>
                                            <div className="pr-4 flex items-center gap-2">
                                                <SaveTestButton scenario={scenario} projectId={projectId} />
                                                <RunTestButton
                                                    scenario={scenario}
                                                    router={router}
                                                    environmentState={environmentState}
                                                    runReadiness={runReadiness}
                                                />
                                            </div>
                                        </div>
                                            );
                                        })()}
                                        <AccordionContent className="px-4 pb-4 pt-0">
                                            <div className="pl-4 border-l-2 border-slate-800 ml-1 space-y-2 mt-2">
                                                {(scenario.steps || []).map((step, idx) => {
                                                    const stepObject = typeof step === 'string' ? null : step;
                                                    return (
                                                        <div key={idx} className="flex gap-3 text-sm text-slate-400 items-start">
                                                            <span className="font-mono text-xs text-slate-600 select-none mt-0.5">
                                                                {(idx + 1).toString().padStart(2, '0')}
                                                            </span>
                                                            <div className="flex-1">
                                                                {stepObject?.step_type && (
                                                                    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium mr-2 ${stepObject.step_type === 'API'
                                                                        ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20'
                                                                        : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                                                                        }`}>
                                                                        {stepObject.step_type === 'API' ? '🌐 API' : '👁️ UI'}
                                                                    </span>
                                                                )}
                                                                <span>
                                                                    {stepObject?.description || (typeof step === 'string' ? step : JSON.stringify(step))}
                                                                </span>
                                                            </div>
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        </AccordionContent>
                                    </AccordionItem>
                                ))}
                            </Accordion>
                        </div>
                    </ScrollArea>
                )}
            </div>
        </div>
    );
}

type AppRouter = ReturnType<typeof useRouter>;

type GeneratedScenarioStep = GeneratedScenario["steps"][number];

const getStepText = (step: GeneratedScenarioStep): string => {
    if (typeof step === "string") return step;
    return step.description || step.action || "";
};

const RunTestButton = ({
    scenario,
    router,
    environmentState,
    runReadiness,
}: {
    scenario: GeneratedScenario;
    router: AppRouter;
    environmentState: EnvironmentReadinessState;
    runReadiness: ScenarioRunReadiness;
}) => {
    const [loading, setLoading] = useState(false);

    const handleRun = async (e: React.MouseEvent) => {
        e.stopPropagation(); // Prevent Accordion toggle
        if (loading || runReadiness.status !== "ready") return;
        setLoading(true);

        try {
            const requiredVariables = getScenarioRequiredVariables(scenario);
            const defaultEnvironment = environmentState.status === "ready" ? environmentState.env : null;

            if (requiredVariables.length > 0 && !defaultEnvironment) {
                throw new Error("默认环境未就绪，无法运行依赖变量的场景。");
            }

            // Mapping GeneratedScenario to Ad-hoc Case format expected by backend
            const inferredMode = scenario.steps.some((s) => typeof s !== "string" && s.step_type === "API")
                ? (scenario.steps.some((s) => typeof s !== "string" && s.step_type === "UI") ? "HYBRID" : "API")
                : "UI";

            const adhocCase = {
                id: scenario.scenario_id,
                name: scenario.name || `场景 (Scenario) ${scenario.scenario_id}`,
                priority: scenario.priority,
                required_variables: requiredVariables,
                mode: inferredMode,
                steps: scenario.steps.map(s => {
                    if (typeof s === 'string') return { description: s };
                    return {
                        description: s.description,
                        step_type: s.step_type,
                        action: s.action,
                        target: s.target,
                        value: s.value,
                        method: s.method,
                        url: s.url,
                        url_path: s.url_path,
                        body: s.body,
                        input_data: s.input_data,
                        expected_result: s.expected_result,
                        expected_status_code: s.expected_status_code,
                        json_assertions: s.json_assertions,
                        extract: s.extract,
                        payload: s.payload,
                    };
                }),
                tags: ["adhoc", "neural-design"]
            };

            const res = await fetch("/api/v1/executions", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    tc_ids: [scenario.scenario_id],
                    mode: "normal",
                    parallel: false,
                    env: defaultEnvironment?.id,
                    dynamic_payload: [adhocCase] // Pass the full data!
                })
            });

            if (!res.ok) {
                const rawText = await res.text();
                try {
                    const parsed = JSON.parse(rawText);
                    const detail = parsed?.detail;
                    if (detail?.code === "missing_execution_variables") {
                        const missing = Array.isArray(detail.missing_variables) ? detail.missing_variables.join(", ") : "";
                        throw new Error(`执行缺少变量: ${missing}`);
                    }
                    throw new Error(detail?.message || rawText || "执行启动失败");
                } catch {
                    throw new Error(rawText || "执行启动失败 (Failed to start execution)");
                }
            }

            const data = await res.json();

            toast.success("任务下发成功！ (Task dispatched!)", {
                description: `Execution ID: ${data.execution_id}`,
                action: {
                    label: "去查看 (View)",
                    onClick: () => router.push("/executions")
                },
                duration: 5000,
            });
        } catch (error) {
            toast.error("执行失败 (Execution Failed)", {
                description: String(error)
            });
        } finally {
            setLoading(false);
        }
    };

    return (
        <Button
            variant="outline"
            size="sm"
            className="h-7 text-xs transition-all border-purple-500/30 bg-purple-500/5 text-purple-400 hover:text-purple-300 hover:bg-purple-500/20 hover:border-purple-500/50 shadow-sm shadow-purple-900/10"
            onClick={handleRun}
            disabled={loading || runReadiness.status !== "ready"}
            title={runReadiness.status === "ready" ? "立即运行" : runReadiness.label}
        >
            {loading ? (
                <>
                    <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                    运行中... (Running...)
                </>
            ) : runReadiness.status !== "ready" ? (
                <>不可运行 (Blocked)</>
            ) : (
                <>
                    一键运行 (Run)
                </>
            )}
        </Button>
    );
};

// Helper: Save Test to DB
const SaveTestButton = ({ scenario, projectId }: { scenario: GeneratedScenario, projectId: string }) => {
    const [saving, setSaving] = useState(false);
    const [saved, setSaved] = useState(false);

    const handleSave = async (e: React.MouseEvent) => {
        e.stopPropagation();
        if (saving || saved) return;
        setSaving(true);
        try {
            const isUI = (scenario.steps || []).some((s) => {
                if (typeof s !== "string" && s.step_type === "UI") return true;
                const text = getStepText(s);
                return text.includes('点击') || text.includes('页面') || text.includes('访问') || text.includes('Logo') || text.includes('URL') || text.includes('输入');
            }) || (scenario.name || "").includes('UI') || (scenario.name || "").includes('页面') || (scenario.description || "").includes('UI');

            if (isUI) {
                // UI Smart Routing -> Visual Use Case
                await visualUiService.importFromDesign({
                    name: scenario.name || `场景 (Scenario) ${scenario.scenario_id}`,
                    description: scenario.description || "",
                    steps: scenario.steps,
                    project_id: projectId
                });

                setSaved(true);
                toast.success("保存成功-UI分流 (Saved (UI Route))", {
                    description: "已成功转入视觉UI用例库 (Successfully saved to Visual UI case library)",
                    duration: 4000,
                });
            } else {
                // API Smart Routing -> Standard API Use Case
                const tcData = {
                    name: scenario.name || `场景 (Scenario) ${scenario.scenario_id}`,
                    description: scenario.description || "",
                    mode: "API",
                    priority: scenario.priority?.toUpperCase() || "P1",
                    steps: (scenario.steps || []).map((s) => {
                        const desc = typeof s === 'string' ? s : s.description;
                        return {
                            name: desc,
                            method: typeof s === 'string' ? "GET" : (s.method || "GET"),
                            url: typeof s === 'string' ? desc : (s.url || desc),
                            headers: {},
                            body: typeof s === 'string' ? undefined : (s.body || undefined),
                            expected_status_code: typeof s === 'string' ? 200 : (s.expected_status_code || 200),
                            json_assertions: typeof s === 'string' ? {} : (s.json_assertions || {}),
                            assertions: [{ type: "status_code", expected: typeof s === 'string' ? 200 : (s.expected_status_code || 200) }]
                        };
                    }),
                    tags: ["auto-generated", "neural-design"]
                };

                const res = await fetch("/api/v1/test-cases", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(tcData),
                });

                if (!res.ok) throw new Error("保存API测试用例失败 (Failed to save API test case)");

                setSaved(true);
                toast.success("保存成功-API分流 (Saved (API Route))", {
                    description: "已将该API用例加入主流测试库 (API case added to main test library)",
                    duration: 4000,
                });
            }
        } catch (error) {
            toast.error("保存失败 (Save Failed)", {
                description: String(error)
            });
        } finally {
            setSaving(false);
        }
    };

    return (
        <Button
            variant="outline"
            size="sm"
            className={`h-7 text-xs transition-all ${saved ? "border-green-500/30 bg-green-500/10 text-green-400 pointer-events-none" : "border-blue-500/30 bg-blue-500/5 text-blue-400 hover:text-blue-300 hover:bg-blue-500/20 hover:border-blue-500/50 shadow-sm shadow-blue-900/10"}`}
            onClick={handleSave}
            disabled={saving || saved}
        >
            {saving ? (
                <>
                    <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                    保存... (Saving...)
                </>
            ) : saved ? (
                <>已保存 (Saved)</>
            ) : (
                <>保存入库 (Save)</>
            )}
        </Button>
    );
};
