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
        toast.success("准备调度引擎... (Preparing engine...)", { description: "正在推送到 Midscene 视觉执行器 (Pushing to Midscene visual executor)" });
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
        if (status === 'active') return 'border-emerald-500/40 bg-emerald-500/10 text-emerald-200';
        if (status === 'archived') return 'border-slate-600 bg-slate-800 text-slate-300';
        return 'border-amber-500/40 bg-amber-500/10 text-amber-200';
    };

    const renderCaseSkeletons = () => (
        <div className="space-y-2 p-2">
            {[0, 1, 2, 3].map((item) => (
                <div key={item} className="rounded-md border border-slate-800 bg-slate-900/60 p-3 space-y-3">
                    <Skeleton className="h-4 w-3/4 bg-slate-800" />
                    <div className="flex justify-between gap-3">
                        <Skeleton className="h-5 w-16 bg-slate-800" />
                        <Skeleton className="h-4 w-20 bg-slate-800" />
                    </div>
                </div>
            ))}
        </div>
    );

    const renderEmptyCases = () => (
        <div className="m-2 rounded-lg border border-dashed border-slate-700 bg-slate-950/60 p-4 text-center space-y-3">
            <div>
                <p className="text-sm font-medium text-slate-200">暂无视觉用例 (No visual cases yet)</p>
                <p className="text-xs text-slate-500 mt-1">创建一个空白用例，或用 AI 生成未保存草稿开始。 (Create one or start with an AI draft.)</p>
            </div>
            <Button size="sm" onClick={handleCreateNew} className="bg-indigo-600 hover:bg-indigo-700 text-white">
                <Plus className="h-4 w-4 mr-2" />
                创建用例 (Create Case)
            </Button>
            <p className="text-[11px] text-violet-300">AI 草稿助手在右侧面板可用。 (AI Draft Assistant is available on the right.)</p>
        </div>
    );

    const renderDraftCard = () => (
        <Collapsible open={draftAssistantOpen} onOpenChange={setDraftAssistantOpen}>
            <Card className="bg-slate-900 border-slate-800 shadow-xl">
                <CollapsibleTrigger asChild>
                    <button type="button" className="w-full text-left">
                        <CardHeader className="pb-3 border-b border-slate-800 hover:bg-slate-800/40 transition-colors">
                            <div className="flex items-start justify-between gap-3">
                                <div className="space-y-2">
                                    <CardTitle className="text-base text-indigo-400 flex items-center gap-2">
                                        <Sparkles className="h-4 w-4" />
                                        AI 生成草稿助手 (AI Draft Assistant)
                                        <Badge variant="outline" className="border-violet-500/40 bg-violet-500/10 text-violet-200">Draft only</Badge>
                                    </CardTitle>
                                    <p className="text-xs text-slate-500">
                                        从自然语言生成未保存草稿；不会自动保存或运行。 (Generate an unsaved draft from natural language.)
                                    </p>
                                </div>
                                <ChevronDown className={`h-4 w-4 shrink-0 text-slate-500 transition-transform ${draftAssistantOpen ? 'rotate-180' : ''}`} />
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
                            className="min-h-24 bg-slate-950 border-slate-700 text-slate-100 placeholder:text-slate-500"
                        />
                        {clarificationQuestions.length > 0 && (
                            <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200">
                                <div className="font-medium mb-1">需要补充信息 (More details needed)</div>
                                <ul className="list-disc pl-5 space-y-1">
                                    {clarificationQuestions.map((question, index) => (
                                        <li key={`${question}-${index}`}>{question}</li>
                                    ))}
                                </ul>
                            </div>
                        )}
                        <div className="flex justify-end">
                            <Button onClick={handleGenerateDraft} disabled={isGeneratingDraft} className="bg-violet-600 hover:bg-violet-700 text-white">
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
        <div className="flex-1 flex flex-col lg:flex-row overflow-hidden min-h-screen bg-slate-950 text-slate-200">
            {/* Left Panel: Case Explorer */}
            <div className="w-full lg:w-80 lg:shrink-0 border-b lg:border-b-0 lg:border-r border-slate-800 bg-slate-900 flex flex-col h-auto lg:h-full max-h-[40vh] lg:max-h-none">
                <div className="p-4 border-b border-slate-800 flex items-center justify-between">
                    <h2 className="font-semibold flex items-center gap-2 text-slate-200">
                        <Eye className="h-5 w-5 text-indigo-500" />
                        视觉UI套件 (Visual UI Suite)
                    </h2>
                    <Button size="icon" variant="ghost" onClick={handleCreateNew} aria-label="创建新视觉用例 (Create new visual case)">
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
                                className={`p-3 rounded-md cursor-pointer border transition-colors group ${activeCaseId === vc.id ? 'border-indigo-500 bg-indigo-500/10 text-slate-200' : 'border-transparent bg-transparent hover:bg-slate-800/50 text-slate-300'}`}
                            >
                                <div className="flex justify-between items-start">
                                    <div className="truncate font-medium text-sm">{vc.name}</div>
                                    <Button
                                        size="icon"
                                        variant="ghost"
                                        aria-label={`删除视觉用例 ${vc.name} (Delete visual case ${vc.name})`}
                                        className="h-8 w-8 text-rose-400 opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity hover:text-rose-500 hover:bg-rose-500/10"
                                        onClick={(e) => handleDeleteClick(vc.id, e)}
                                    >
                                        <Trash2 className="h-4 w-4" />
                                    </Button>
                                </div>
                                <div className="text-xs text-slate-500 mt-2 flex items-center justify-between gap-2">
                                    <div className="flex items-center gap-1.5">
                                        <Badge variant="outline" className="border-slate-700 bg-slate-950 text-slate-300">{vc.steps.length} 步 (Steps)</Badge>
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
                                <h1 className="text-2xl font-bold text-slate-100">{currentName || "未命名用例 (Untitled Case)"}</h1>
                                <p className="text-slate-400 text-sm mt-1">{activeCaseId === 'NEW' ? '创建新用例草稿 (New Case Draft)' : `ID: ${activeCaseId}`}</p>
                            </div>
                            <div className="flex flex-wrap items-center gap-3">
                                <Button variant="outline" onClick={handleSave} disabled={isSaving} aria-label="保存视觉用例 (Save visual case)" className="border-slate-700 bg-slate-900 text-slate-300 hover:bg-slate-800 hover:text-slate-100">
                                    <Save className="h-4 w-4 mr-2" />
                                    {isSaving ? "保存中... (Saving...)" : "保存用例 (Save Case)"}
                                </Button>
                                <Button onClick={handleExecute} disabled={isExecuting} aria-label="运行并追踪视觉用例 (Run and track visual case)" className="bg-indigo-600 hover:bg-indigo-700 text-white">
                                    <Play className="h-4 w-4 mr-2" />
                                    {isExecuting ? "启动中... (Starting...)" : "运行并追踪 (Run & Track)"}
                                </Button>
                            </div>
                        </div>

                        {/* Meta Fields Map */}
                        {/* Meta Fields Map */}
                        <Card className="bg-slate-900 border-slate-800 shadow-xl">
                            <CardHeader className="pb-3 border-b border-slate-800">
                                <CardTitle className="text-base text-indigo-400">用例属性设定 (Case Metadata)</CardTitle>
                            </CardHeader>
                            <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4">
                                <div className="space-y-1.5">
                                    <label htmlFor="visual-case-name" className="text-sm font-medium text-slate-400">用例名称 (Case Name)</label>
                                    <Input id="visual-case-name" value={currentName} onChange={e => setCurrentName(e.target.value)} aria-describedby="visual-case-name-help" className="bg-slate-950 border-slate-700 text-slate-100 placeholder:text-slate-500" />
                                    <p id="visual-case-name-help" className="text-xs text-slate-500">用于左侧列表和执行报告识别该用例。 (Shown in the case list and reports.)</p>
                                </div>
                                <div className="space-y-1.5">
                                    <label htmlFor="visual-case-base-url" className="text-sm font-medium text-slate-400">默认环境变量 (Base URL)</label>
                                    <Input id="visual-case-base-url" value={currentBaseUrl} onChange={e => setCurrentBaseUrl(e.target.value)} aria-describedby="visual-case-base-url-help" placeholder="https://example.com" className="bg-slate-950 border-slate-700 text-slate-100 placeholder:text-slate-500" />
                                    <p id="visual-case-base-url-help" className="text-xs text-slate-500">GOTO 步骤未填 URL 时会优先使用这里。 (Used by GOTO when no URL is set.)</p>
                                </div>
                                <div className="md:col-span-2 space-y-1.5">
                                    <label htmlFor="visual-case-description" className="text-sm font-medium text-slate-400">用例描述 (Case Description)</label>
                                    <Input id="visual-case-description" value={currentDesc} onChange={e => setCurrentDesc(e.target.value)} aria-describedby="visual-case-description-help" placeholder="记录登录/付款等业务逻辑 (e.g. Login/Payment flow)" className="bg-slate-950 border-slate-700 text-slate-100 placeholder:text-slate-500" />
                                    <p id="visual-case-description-help" className="text-xs text-slate-500">记录业务目的，便于人工确认 AI 草稿。 (Describe the business goal for review.)</p>
                                </div>
                            </CardContent>
                        </Card>

                        {/* DnD Step Builder */}
                        {/* DnD Step Builder */}
                        <Card className="bg-slate-900 border-slate-800 shadow-xl overflow-hidden">
                            <CardContent className="pt-6">
                                <StepBuilder steps={currentSteps} onChange={setCurrentSteps} />
                            </CardContent>
                        </Card>

                    </div>
                ) : (
                    <div className="max-w-5xl mx-auto space-y-6">
                        {renderDraftCard()}
                        <div className="h-full flex flex-col items-center justify-center text-muted-foreground py-24">
                            <Eye className="h-16 w-16 mb-4 text-slate-700 opacity-50" />
                            <p className="text-lg">选择左侧用例、点击+或用 AI 生成草稿开始编排 (Select a case, click +, or generate an AI draft)</p>
                        </div>
                    </div>
                )}
            </div>
            <AlertDialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
                <AlertDialogContent className="bg-slate-900 border-slate-800 text-slate-200">
                    <AlertDialogHeader>
                        <AlertDialogTitle>确定删除此视觉用例吗？ (Delete this visual case?)</AlertDialogTitle>
                        <AlertDialogDescription className="text-slate-400">
                            此操作不可逆，将永久删除该用例的所有业务步骤与数据。 (This action is irreversible. All steps and data will be permanently deleted.)
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel className="bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700 hover:text-slate-200">取消 (Cancel)</AlertDialogCancel>
                        <AlertDialogAction onClick={confirmDelete} className="bg-rose-600 hover:bg-rose-700 text-white border-none">
                            确定删除 (Confirm Delete)
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
            <AlertDialog open={draftConfirmOpen} onOpenChange={setDraftConfirmOpen}>
                <AlertDialogContent className="bg-slate-900 border-slate-800 text-slate-200">
                    <AlertDialogHeader>
                        <AlertDialogTitle>用 AI 草稿覆盖当前编辑内容？ (Replace current editor content?)</AlertDialogTitle>
                        <AlertDialogDescription className="text-slate-400">
                            新草稿会替换右侧编辑器里的名称、Base URL 和步骤；不会自动保存或运行。 (The draft replaces the editor content only; it will not save or run automatically.)
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel className="bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700 hover:text-slate-200">保留当前内容 (Keep Current)</AlertDialogCancel>
                        <AlertDialogAction onClick={() => pendingDraft && applyDraft(pendingDraft)} className="bg-violet-600 hover:bg-violet-700 text-white border-none">
                            使用新草稿 (Use Draft)
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    );
}
