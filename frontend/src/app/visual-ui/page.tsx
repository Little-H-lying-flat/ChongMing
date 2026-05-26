"use client"

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Skeleton } from "@/components/ui/skeleton";
import { ChevronDown, Save, Play, Plus, Trash2, Eye, Sparkles } from "lucide-react";
import { format } from "date-fns";
import { toast } from "sonner";

import { buildVisualExecutionPayload, visualUiService, VisualCaseDraft, VisualUseCase, VisualStep } from '@/services/visualUiService';
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { StepBuilder } from '@/components/visual-ui/StepBuilder';

const DEFAULT_PROJECT_ID = "proj-1"; // Dummy for MVP

export default function VisualUIPage() {
    const router = useRouter();

    const [cases, setCases] = useState<VisualUseCase[]>([]);
    const [activeCaseId, setActiveCaseId] = useState<string | null>(null);

    const [currentName, setCurrentName] = useState("");
    const [currentDesc, setCurrentDesc] = useState("");
    const [currentBaseUrl, setCurrentBaseUrl] = useState("");
    const [currentSteps, setCurrentSteps] = useState<VisualStep[]>([]);

    const [isSaving, setIsSaving] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [isExecuting, setIsExecuting] = useState(false);
    const [draftPrompt, setDraftPrompt] = useState("");
    const [isGeneratingDraft, setIsGeneratingDraft] = useState(false);
    const [clarificationQuestions, setClarificationQuestions] = useState<string[]>([]);
    const [pendingDraft, setPendingDraft] = useState<VisualCaseDraft | null>(null);
    const [draftAssistantOpen, setDraftAssistantOpen] = useState(true);

    const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
    const [caseToDelete, setCaseToDelete] = useState<string | null>(null);
    const [draftConfirmOpen, setDraftConfirmOpen] = useState(false);

    useEffect(() => {
        loadCases();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const loadCases = async () => {
        setIsLoading(true);
        try {
            const res = await visualUiService.getCases(); // Load all cases regardless of project
            setCases(res.data);
            if (res.data.length > 0 && !activeCaseId) {
                selectCase(res.data[0]);
            }
        } catch (err: unknown) {
            // Check if it's a network error to avoid the Next.js Turbopack dev overlay crash
            const error = err as { message?: string };
            if (error?.message?.includes("Failed to fetch")) {
                toast.error("加载失败 (Load Failed)", { description: "请检查后端服务是否已完全启动 (Check if backend is running)" });
            } else {
                toast.error("加载失败 (Load Failed)", { description: error.message });
            }
        } finally {
            setIsLoading(false);
        }
    };

    const selectCase = (vc: VisualUseCase) => {
        setActiveCaseId(vc.id);
        setCurrentName(vc.name);
        setCurrentDesc(vc.description || "");
        setCurrentBaseUrl(vc.base_url || "");

        // Ensure local state has valid IDs for DnD
        const mappedSteps = (vc.steps || []).map((s, i) => ({
            ...s,
            id: s.id || `view_step_${i}`
        }));
        setCurrentSteps(mappedSteps);
        setDraftAssistantOpen(false);
    };

    const handleCreateNew = () => {
        setActiveCaseId("NEW");
        setCurrentName("未命名视觉用例 (Untitled Visual Case)");
        setCurrentDesc("");
        setCurrentBaseUrl("");
        setCurrentSteps([{
            id: `new_start`,
            step_index: 0,
            action: 'GOTO',
            value: 'https://'
        }]);
        setDraftAssistantOpen(false);
    };

    const handleDeleteClick = (id: string, e: React.MouseEvent) => {
        e.stopPropagation();
        setCaseToDelete(id);
        setDeleteConfirmOpen(true);
    };

    const applyDraft = (draft: VisualCaseDraft) => {
        const timestamp = Date.now();
        setActiveCaseId("NEW");
        setCurrentName(draft.name);
        setCurrentDesc(draft.description || "");
        setCurrentBaseUrl(draft.base_url || "");
        setCurrentSteps((draft.steps || []).map((step, index) => ({
            ...step,
            id: `ai_step_${timestamp}_${index}`,
            step_index: index,
        })));
        setPendingDraft(null);
        setDraftConfirmOpen(false);
        toast.success("已生成草稿，请确认后保存 (Draft generated. Review before saving)");
    };

    const hasEditorContent = () => (
        Boolean(currentName.trim()) ||
        Boolean(currentDesc.trim()) ||
        Boolean(currentBaseUrl.trim()) ||
        currentSteps.length > 0
    );

    const handleGenerateDraft = async () => {
        const prompt = draftPrompt.trim();
        if (!prompt) {
            toast.error("请先输入测试需求 (Please enter a test requirement)");
            return;
        }

        setIsGeneratingDraft(true);
        setClarificationQuestions([]);
        try {
            const res = await visualUiService.generateDraft({
                prompt,
                project_id: DEFAULT_PROJECT_ID,
                base_url: currentBaseUrl || undefined,
            });
            if (res.data.status === 'needs_clarification') {
                setClarificationQuestions(res.data.questions || []);
                setDraftAssistantOpen(true);
                toast.error("需要补充信息 (More details needed)");
                return;
            }

            const draft = res.data.draft;
            if (!draft) {
                toast.error("生成失败 (Generation failed)");
                return;
            }

            if (hasEditorContent()) {
                setPendingDraft(draft);
                setDraftConfirmOpen(true);
                return;
            }

            applyDraft(draft);
        } catch (err: unknown) {
            toast.error("生成失败 (Generation Failed)", { description: (err as { message?: string }).message });
        } finally {
            setIsGeneratingDraft(false);
        }
    };

    const confirmDelete = async () => {
        if (!caseToDelete) return;
        try {
            await visualUiService.deleteCase(caseToDelete);
            toast.success("已删除 (Deleted)");
            if (activeCaseId === caseToDelete) setActiveCaseId(null);
            loadCases();
        } catch (err: unknown) {
            toast.error("删除失败 (Delete Failed)", { description: (err as { message?: string }).message });
        } finally {
            setDeleteConfirmOpen(false);
            setCaseToDelete(null);
        }
    };

    const handleSave = async () => {
        setIsSaving(true);
        try {
            // Normalize steps for backend
            const sanitizedSteps = currentSteps.map((s, i) => ({
                step_index: i,
                action: s.action,
                target_description: s.target_description,
                value: s.value,
                screenshot_baseline: s.screenshot_baseline
            }));

            const payload = {
                project_id: DEFAULT_PROJECT_ID,
                name: currentName,
                description: currentDesc,
                base_url: currentBaseUrl,
                status: "active" as const,
                steps: sanitizedSteps
            };

            let savedCase;
            if (activeCaseId === "NEW") {
                const res = await visualUiService.createCase(payload);
                savedCase = res.data;
                toast.success("创建成功 (Created)");
            } else {
                const res = await visualUiService.updateCase(activeCaseId!, payload);
                savedCase = res.data;
                toast.success("更新成功 (Updated)");
            }

            await loadCases();
            selectCase(savedCase);

        } catch (err: unknown) {
            toast.error("保存失败 (Save Failed)", { description: (err as { message?: string }).message });
        } finally {
            setIsSaving(false);
        }
    };

    const handleExecute = async () => {
        if (!activeCaseId || activeCaseId === 'NEW') {
            toast.error("请先保存用例再执行 (Please save the case before running)");
            return;
        }
        if (isExecuting) return;

        setIsExecuting(true);
        toast.success("准备调度引擎... (Preparing engine...)", { description: "正在推送到统一的 Midscene 视觉执行器 (Pushing to the unified Midscene visual executor)" });
        try {
            const execRes = await visualUiService.executeAdhoc(buildVisualExecutionPayload({
                id: activeCaseId,
                name: currentName,
                description: currentDesc,
                base_url: currentBaseUrl,
                steps: currentSteps,
            }));

            const execData = execRes.data as { execution_id?: string } | undefined;
            const execId = execData?.execution_id;

            if (execId) {
                router.push(`/visual-ui/scenario/${execId}`);
            }
        } catch (err: unknown) {
            toast.error("执行启动失败 (Execution Start Failed)", { description: (err as { message?: string }).message });
        } finally {
            setIsExecuting(false);
        }
    };

    const statusBadgeClass = (status: VisualUseCase['status']) => {
        if (status === 'active') return 'border-emerald-200 bg-emerald-50 text-emerald-700';
        if (status === 'archived') return 'border-slate-200 bg-slate-100 text-slate-600';
        return 'border-amber-200 bg-amber-50 text-amber-700';
    };

    const renderCaseSkeletons = () => (
        <div className="space-y-2 p-2">
            {[0, 1, 2, 3].map((item) => (
                <div key={item} className="rounded-xl border border-sky-100 bg-white/70 p-3 space-y-3 shadow-sm">
                    <Skeleton className="h-4 w-3/4 bg-sky-100" />
                    <div className="flex justify-between gap-3">
                        <Skeleton className="h-5 w-16 bg-sky-100" />
                        <Skeleton className="h-4 w-20 bg-slate-100" />
                    </div>
                </div>
            ))}
        </div>
    );

    const renderEmptyCases = () => (
        <div className="m-2 rounded-2xl border border-dashed border-sky-200 bg-white/70 p-4 text-center space-y-3 shadow-sm">
            <div>
                <p className="text-sm font-medium text-slate-900">暂无视觉用例 (No visual cases yet)</p>
                <p className="text-xs text-slate-500 mt-1">创建一个空白用例，或用 AI 生成未保存草稿开始。 (Create one or start with an AI draft.)</p>
            </div>
            <Button size="sm" onClick={handleCreateNew} className="bg-gradient-to-r from-sky-500 via-blue-500 to-violet-500 text-white shadow-lg shadow-sky-500/20 hover:from-sky-600 hover:via-blue-600 hover:to-violet-600">
                <Plus className="h-4 w-4 mr-2" />
                创建用例 (Create Case)
            </Button>
            <p className="text-[11px] text-violet-600">AI 草稿助手在右侧面板可用。 (AI Draft Assistant is available on the right.)</p>
        </div>
    );

    const renderDraftCard = () => (
        <Collapsible open={draftAssistantOpen} onOpenChange={setDraftAssistantOpen}>
            <Card className="overflow-hidden rounded-2xl border-white/70 bg-white/80 shadow-[0_24px_70px_-32px_rgba(124,58,237,0.45)] backdrop-blur-xl">
                <CollapsibleTrigger asChild>
                    <button type="button" className="w-full text-left">
                        <CardHeader className="border-b border-violet-100 bg-gradient-to-r from-violet-50 via-fuchsia-50 to-sky-50 pb-3 transition-colors hover:from-violet-100 hover:via-fuchsia-50 hover:to-sky-100">
                            <div className="flex items-start justify-between gap-3">
                                <div className="space-y-2">
                                    <CardTitle className="text-base text-violet-700 flex items-center gap-2">
                                        <Sparkles className="h-4 w-4" />
                                        AI 生成草稿助手 (AI Draft Assistant)
                                        <Badge variant="outline" className="border-violet-200 bg-violet-100 text-violet-700">Draft only</Badge>
                                    </CardTitle>
                                    <p className="text-xs text-slate-600">
                                        从自然语言生成未保存草稿；不会自动保存或运行。 (Generate an unsaved draft from natural language.)
                                    </p>
                                </div>
                                <ChevronDown className={`h-4 w-4 shrink-0 text-violet-500 transition-transform ${draftAssistantOpen ? 'rotate-180' : ''}`} />
                            </div>
                        </CardHeader>
                    </button>
                </CollapsibleTrigger>
                <CollapsibleContent>
                    <CardContent className="space-y-3 pt-4">
                        <Textarea
                            value={draftPrompt}
                            onChange={e => setDraftPrompt(e.target.value)}
                            placeholder="例如：打开登录页，输入用户名和密码，点击登录，验证进入首页。 (Describe the UI flow to draft)"
                            className="min-h-24 border-violet-200 bg-white/85 text-slate-900 placeholder:text-slate-400 focus-visible:ring-violet-400"
                        />
                        {clarificationQuestions.length > 0 && (
                            <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                                <div className="font-medium mb-1">需要补充信息 (More details needed)</div>
                                <ul className="list-disc pl-5 space-y-1">
                                    {clarificationQuestions.map((question, index) => (
                                        <li key={`${question}-${index}`}>{question}</li>
                                    ))}
                                </ul>
                            </div>
                        )}
                        <div className="flex justify-end">
                            <Button onClick={handleGenerateDraft} disabled={isGeneratingDraft} className="bg-gradient-to-r from-violet-500 to-fuchsia-500 text-white shadow-lg shadow-violet-500/25 hover:from-violet-600 hover:to-fuchsia-600">
                                <Sparkles className="h-4 w-4 mr-2" />
                                {isGeneratingDraft ? "生成中... (Generating...)" : "生成未保存草稿 (Generate Draft)"}
                            </Button>
                        </div>
                    </CardContent>
                </CollapsibleContent>
            </Card>
        </Collapsible>
    );

    return (
        <div className="flex-1 flex flex-col lg:flex-row overflow-hidden min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(56,189,248,0.18),transparent_30%),radial-gradient(circle_at_top_right,rgba(168,85,247,0.14),transparent_28%),linear-gradient(135deg,#f8fafc_0%,#eef6ff_45%,#fff7ed_100%)] text-slate-900">
            {/* Left Panel: Case Explorer */}
            <div className="w-full lg:w-80 lg:shrink-0 border-b lg:border-b-0 lg:border-r border-sky-100/80 bg-white/75 backdrop-blur-xl shadow-[12px_0_40px_-28px_rgba(14,165,233,0.5)] flex flex-col h-auto lg:h-full max-h-[40vh] lg:max-h-none">
                <div className="p-4 border-b border-sky-100 flex items-center justify-between">
                    <h2 className="font-semibold flex items-center gap-2 text-slate-900">
                        <span className="rounded-xl bg-sky-100 p-1.5 text-sky-700" aria-hidden="true">
                            <Eye className="h-4 w-4" />
                        </span>
                        视觉UI套件 (Visual UI Suite)
                    </h2>
                    <Button size="icon" variant="ghost" onClick={handleCreateNew} aria-label="创建新视觉用例 (Create new visual case)" className="text-sky-700 hover:bg-sky-50 hover:text-sky-800">
                        <Plus className="h-4 w-4" />
                    </Button>
                </div>
                <div className="flex-1 overflow-y-auto p-2 space-y-1">
                    {isLoading ? (
                        renderCaseSkeletons()
                    ) : cases.length === 0 ? (
                        renderEmptyCases()
                    ) : (
                        cases.map(vc => (
                            <div
                                key={vc.id}
                                onClick={() => selectCase(vc)}
                                className={`p-3 rounded-xl cursor-pointer border transition-all group ${activeCaseId === vc.id ? 'border-sky-300 bg-gradient-to-r from-sky-100 via-white to-violet-100 text-slate-950 shadow-sm ring-1 ring-sky-200' : 'border-transparent bg-white/30 text-slate-700 hover:border-sky-200 hover:bg-white/80 hover:shadow-sm'}`}
                            >
                                <div className="flex justify-between items-start">
                                    <div className="truncate font-medium text-sm">{vc.name}</div>
                                    <Button
                                        size="icon"
                                        variant="ghost"
                                        aria-label={`删除视觉用例 ${vc.name} (Delete visual case ${vc.name})`}
                                        className="h-8 w-8 text-rose-500 opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity hover:bg-rose-50 hover:text-rose-700"
                                        onClick={(e) => handleDeleteClick(vc.id, e)}
                                    >
                                        <Trash2 className="h-4 w-4" />
                                    </Button>
                                </div>
                                <div className="text-xs text-slate-500 mt-2 flex items-center justify-between gap-2">
                                    <div className="flex items-center gap-1.5">
                                        <Badge variant="outline" className="border-sky-200 bg-sky-50 text-sky-700">{vc.steps.length} 步 (Steps)</Badge>
                                        <Badge variant="outline" className={statusBadgeClass(vc.status)}>{vc.status}</Badge>
                                    </div>
                                    <span className="shrink-0">{format(new Date(vc.updated_at), 'MM-dd HH:mm')}</span>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </div>

            {/* Right Panel: Canvas Editor */}
            <div className="flex-1 overflow-y-auto p-4 lg:p-6 min-w-0">
                {activeCaseId ? (
                    <div className="max-w-5xl mx-auto space-y-6">
                        {renderDraftCard()}

                        {/* Header Controls */}
                        <div className="flex items-center justify-between">
                            <div>
                                <h1 className="text-2xl font-bold text-slate-950">{currentName || "未命名用例 (Untitled Case)"}</h1>
                                <p className="text-slate-500 text-sm mt-1">{activeCaseId === 'NEW' ? '创建新用例草稿 (New Case Draft)' : `ID: ${activeCaseId}`}</p>
                            </div>
                            <div className="flex flex-wrap items-center gap-3">
                                <Button variant="outline" onClick={handleSave} disabled={isSaving} aria-label="保存视觉用例 (Save visual case)" className="border-sky-200 bg-white/75 text-slate-700 shadow-sm hover:bg-sky-50 hover:text-sky-800">
                                    <Save className="h-4 w-4 mr-2" />
                                    {isSaving ? "保存中... (Saving...)" : "保存用例 (Save Case)"}
                                </Button>
                                <Button onClick={handleExecute} disabled={isExecuting} aria-label="运行并追踪视觉用例 (Run and track visual case)" className="bg-gradient-to-r from-sky-500 via-blue-500 to-violet-500 text-white shadow-lg shadow-sky-500/25 hover:from-sky-600 hover:via-blue-600 hover:to-violet-600">
                                    <Play className="h-4 w-4 mr-2" />
                                    {isExecuting ? "启动中... (Starting...)" : "运行并追踪 (Run & Track)"}
                                </Button>
                            </div>
                        </div>

                        {/* Meta Fields Map */}
                        {/* Meta Fields Map */}
                        <Card className="rounded-2xl border-white/70 bg-white/80 shadow-[0_20px_60px_-35px_rgba(15,23,42,0.35)] backdrop-blur-xl">
                            <CardHeader className="pb-3 border-b border-sky-100 bg-gradient-to-r from-sky-50 to-white">
                                <CardTitle className="text-base text-sky-700">用例属性设定 (Case Metadata)</CardTitle>
                            </CardHeader>
                            <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4">
                                <div className="space-y-1.5">
                                    <label htmlFor="visual-case-name" className="text-sm font-medium text-slate-700">用例名称 (Case Name)</label>
                                    <Input id="visual-case-name" value={currentName} onChange={e => setCurrentName(e.target.value)} aria-describedby="visual-case-name-help" className="border-sky-200 bg-white text-slate-900 placeholder:text-slate-400 focus-visible:ring-sky-400" />
                                    <p id="visual-case-name-help" className="text-xs text-slate-500">用于左侧列表和执行报告识别该用例。 (Shown in the case list and reports.)</p>
                                </div>
                                <div className="space-y-1.5">
                                    <label htmlFor="visual-case-base-url" className="text-sm font-medium text-slate-700">默认环境变量 (Base URL)</label>
                                    <Input id="visual-case-base-url" value={currentBaseUrl} onChange={e => setCurrentBaseUrl(e.target.value)} aria-describedby="visual-case-base-url-help" placeholder="https://example.com" className="border-sky-200 bg-white text-slate-900 placeholder:text-slate-400 focus-visible:ring-sky-400" />
                                    <p id="visual-case-base-url-help" className="text-xs text-slate-500">GOTO 步骤未填 URL 时会优先使用这里。 (Used by GOTO when no URL is set.)</p>
                                </div>
                                <div className="md:col-span-2 space-y-1.5">
                                    <label htmlFor="visual-case-description" className="text-sm font-medium text-slate-700">用例描述 (Case Description)</label>
                                    <Input id="visual-case-description" value={currentDesc} onChange={e => setCurrentDesc(e.target.value)} aria-describedby="visual-case-description-help" placeholder="记录登录/付款等业务逻辑 (e.g. Login/Payment flow)" className="border-sky-200 bg-white text-slate-900 placeholder:text-slate-400 focus-visible:ring-sky-400" />
                                    <p id="visual-case-description-help" className="text-xs text-slate-500">记录业务目的，便于人工确认 AI 草稿。 (Describe the business goal for review.)</p>
                                </div>
                            </CardContent>
                        </Card>

                        {/* DnD Step Builder */}
                        {/* DnD Step Builder */}
                        <Card className="overflow-hidden rounded-2xl border-white/70 bg-white/80 shadow-[0_20px_60px_-35px_rgba(14,165,233,0.35)] backdrop-blur-xl">
                            <CardContent className="pt-6">
                                <StepBuilder steps={currentSteps} onChange={setCurrentSteps} />
                            </CardContent>
                        </Card>

                    </div>
                ) : (
                    <div className="max-w-5xl mx-auto space-y-6">
                        {renderDraftCard()}
                        <div className="h-full flex flex-col items-center justify-center rounded-3xl border border-dashed border-sky-200 bg-white/50 py-24 text-center text-slate-500 shadow-sm backdrop-blur">
                            <Eye className="h-16 w-16 mb-4 text-sky-300" />
                            <p className="text-lg text-slate-700">选择左侧用例、点击+或用 AI 生成草稿开始编排 (Select a case, click +, or generate an AI draft)</p>
                        </div>
                    </div>
                )}
            </div>
            <AlertDialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
                <AlertDialogContent className="border-slate-200 bg-white text-slate-900 shadow-2xl">
                    <AlertDialogHeader>
                        <AlertDialogTitle>确定删除此视觉用例吗？ (Delete this visual case?)</AlertDialogTitle>
                        <AlertDialogDescription className="text-slate-600">
                            此操作不可逆，将永久删除该用例的所有业务步骤与数据。 (This action is irreversible. All steps and data will be permanently deleted.)
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel className="border-slate-200 bg-white text-slate-700 hover:bg-slate-50 hover:text-slate-900">取消 (Cancel)</AlertDialogCancel>
                        <AlertDialogAction onClick={confirmDelete} className="bg-rose-600 hover:bg-rose-700 text-white border-none">
                            确定删除 (Confirm Delete)
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
            <AlertDialog open={draftConfirmOpen} onOpenChange={setDraftConfirmOpen}>
                <AlertDialogContent className="border-slate-200 bg-white text-slate-900 shadow-2xl">
                    <AlertDialogHeader>
                        <AlertDialogTitle>用 AI 草稿覆盖当前编辑内容？ (Replace current editor content?)</AlertDialogTitle>
                        <AlertDialogDescription className="text-slate-600">
                            新草稿会替换右侧编辑器里的名称、Base URL 和步骤；不会自动保存或运行。 (The draft replaces the editor content only; it will not save or run automatically.)
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel className="border-slate-200 bg-white text-slate-700 hover:bg-slate-50 hover:text-slate-900">保留当前内容 (Keep Current)</AlertDialogCancel>
                        <AlertDialogAction onClick={() => pendingDraft && applyDraft(pendingDraft)} className="bg-violet-600 hover:bg-violet-700 text-white border-none">
                            使用新草稿 (Use Draft)
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    );
}
