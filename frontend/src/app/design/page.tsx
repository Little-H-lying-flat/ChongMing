"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Brain, FileJson, Layers, Sparkles, Loader2, Play, FileText, AlertCircle, UploadCloud } from "lucide-react";
import { toast } from "sonner";
import { useRouter } from "next/navigation";
import { visualUiService } from "@/services/visualUiService";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
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
    steps: Array<{
        step_type: "API" | "UI";
        description: string;
        method?: string;
        url?: string;
        body?: any;
    } | string>; // Backwards compatibility
}

// --- API ---
const analyzeDesign = async (data: DesignRequest): Promise<GeneratedScenario[]> => {
    const res = await fetch("/api/v1/design/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });

    if (!res.ok) {
        const errorText = await res.text();
        console.error("Analysis Failed:", res.status, res.statusText, errorText);
        throw new Error(`Failed to analyze design: ${res.status} ${res.statusText} - ${errorText.substring(0, 100)}`);
    }

    return res.json();
};

export default function NeuralDesignPage() {
    const router = useRouter();
    const [projectId, setProjectId] = useState("proj_001");
    const [requirement, setRequirement] = useState("");
    const [targetType, setTargetType] = useState<"API" | "UI" | "MIXED">("MIXED");
    const [uploading, setUploading] = useState(false);

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
            if (data.file_type === "json" && data.extracted_text.includes("openapi") || data.extracted_text.includes("paths")) {
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
        mutationFn: analyzeDesign,
        onError: (err) => {
            console.error(err);
            // Optional: integration with toast if available
            // toast.error("Failed to generate scenarios");
        },
    });

    const handleGenerate = () => {
        if (!requirement.trim()) return;
        mutate({
            project_id: projectId,
            requirement_text: requirement,
            context: "", // Optional context
            target_type: targetType
        });
    };

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
                                <h3 className="text-lg font-semibold text-slate-200">
                                    生成的场景 (Generated Scenarios)
                                    <span className="ml-2 text-xs bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded-full">
                                        {scenarios.length}
                                    </span>
                                </h3>
                            </div>

                            <Accordion type="single" collapsible className="w-full space-y-4">
                                {scenarios.map((scenario) => (
                                    <AccordionItem
                                        key={scenario.scenario_id}
                                        value={scenario.scenario_id}
                                        className="bg-slate-900 border border-slate-800 rounded-lg px-2 data-[state=open]:border-blue-500/50 transition-all"
                                    >
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
                                                    </div>
                                                </div>
                                            </AccordionTrigger>
                                            <div className="pr-4 flex items-center gap-2">
                                                <SaveTestButton scenario={scenario as any} projectId={projectId} />
                                                <RunTestButton scenario={scenario as any} router={router} />
                                            </div>
                                        </div>
                                        <AccordionContent className="px-4 pb-4 pt-0">
                                            <div className="pl-4 border-l-2 border-slate-800 ml-1 space-y-2 mt-2">
                                                {(scenario.steps || []).map((step: any, idx) => (
                                                    <div key={idx} className="flex gap-3 text-sm text-slate-400 items-start">
                                                        <span className="font-mono text-xs text-slate-600 select-none mt-0.5">
                                                            {(idx + 1).toString().padStart(2, '0')}
                                                        </span>
                                                        <div className="flex-1">
                                                            {step.step_type && (
                                                                <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium mr-2 ${step.step_type === 'API'
                                                                    ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20'
                                                                    : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                                                                    }`}>
                                                                    {step.step_type === 'API' ? '🌐 API' : '👁️ UI'}
                                                                </span>
                                                            )}
                                                            <span>{step.description || step as string}</span>
                                                        </div>
                                                    </div>
                                                ))}
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

// Helper: Run Test Execution
const RunTestButton = ({ scenario, router }: { scenario: GeneratedScenario, router: any }) => {
    const [loading, setLoading] = useState(false);

    const handleRun = async (e: React.MouseEvent) => {
        e.stopPropagation(); // Prevent Accordion toggle
        if (loading) return;
        setLoading(true);

        try {
            // Mapping GeneratedScenario to Ad-hoc Case format expected by backend
            const adhocCase = {
                id: scenario.scenario_id,
                name: scenario.name || `场景 (Scenario) ${scenario.scenario_id}`,
                priority: scenario.priority,
                mode: "UI", // Default to UI for now, or infer from steps
                steps: scenario.steps.map(s => {
                    if (typeof s === 'string') return { description: s };
                    return {
                        description: s.description,
                        step_type: s.step_type,
                        method: s.method,        // Pass through
                        url: s.url,              // Pass through
                        body: s.body             // Pass through
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
                    dynamic_payload: [adhocCase] // Pass the full data!
                })
            });

            if (!res.ok) throw new Error("执行启动失败 (Failed to start execution)");

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
            disabled={loading}
        >
            {loading ? (
                <>
                    <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                    运行中... (Running...)
                </>
            ) : (
                <>
                    一键运行 (Run)
                </>
            )}
        </Button>
    );
};

// Helper: Save Test to DB
const SaveTestButton = ({ scenario, projectId }: { scenario: any, projectId: string }) => {
    const [saving, setSaving] = useState(false);
    const [saved, setSaved] = useState(false);

    const handleSave = async (e: React.MouseEvent) => {
        e.stopPropagation();
        if (saving || saved) return;
        setSaving(true);
        try {
            const isUI = (scenario.steps || []).some((s: any) => s.step_type === "UI");

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
                    steps: (scenario.steps || []).map((s: any) => {
                        const desc = typeof s === 'string' ? s : s.description;
                        return {
                            action: typeof s === 'string' ? "verify" : (s.method || "verify"),
                            target: typeof s === 'string' ? desc : (s.url || desc),
                            value: typeof s === 'string' ? undefined : (s.body ? JSON.stringify(s.body) : undefined),
                            expected: desc
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
