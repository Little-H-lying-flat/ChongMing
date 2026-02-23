"use client"

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Save, Play, Plus, Trash2, Eye } from "lucide-react";
import { format } from "date-fns";
import { toast } from "sonner";

import { visualUiService, VisualUseCase, VisualStep } from '@/services/visualUiService';
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

    const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
    const [caseToDelete, setCaseToDelete] = useState<string | null>(null);

    useEffect(() => {
        loadCases();
    }, []);

    const loadCases = async () => {
        setIsLoading(true);
        try {
            const res = await visualUiService.getCases(); // Load all cases regardless of project
            setCases(res.data);
            if (res.data.length > 0 && !activeCaseId) {
                selectCase(res.data[0]);
            }
        } catch (err: any) {
            // Check if it's a network error to avoid the Next.js Turbopack dev overlay crash
            if (err?.message?.includes("Failed to fetch")) {
                toast.error("加载失败 (Load Failed)", { description: "请检查后端服务是否已完全启动 (Check if backend is running)" });
            } else {
                toast.error("加载失败 (Load Failed)", { description: err.message });
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
    };

    const handleDeleteClick = (id: string, e: React.MouseEvent) => {
        e.stopPropagation();
        setCaseToDelete(id);
        setDeleteConfirmOpen(true);
    };

    const confirmDelete = async () => {
        if (!caseToDelete) return;
        try {
            await visualUiService.deleteCase(caseToDelete);
            toast.success("已删除 (Deleted)");
            if (activeCaseId === caseToDelete) setActiveCaseId(null);
            loadCases();
        } catch (err: any) {
            toast.error("删除失败 (Delete Failed)", { description: err.message });
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

        } catch (err: any) {
            toast.error("保存失败 (Save Failed)", { description: err.message });
        } finally {
            setIsSaving(false);
        }
    };

    const handleExecute = async () => {
        if (activeCaseId === 'NEW') {
            toast.error("请先保存用例再执行 (Please save the case before running)");
            return;
        }
        toast.success("准备调度引擎... (Preparing engine...)", { description: "正在推送到RightPupil视觉引擎 (Pushing to RightPupil Visual Engine)" });
        try {
            // Fire an Ad-Hoc execution request dynamically converting Steps -> IR -> Celery Task
            // In a real scenario, could call the standard Runner API with mode: 'UI'

            const dynamicIr = {
                id: activeCaseId,
                name: currentName,
                mode: "UI",
                steps: currentSteps.map(s => ({
                    step_type: "UI",
                    action_type: s.action.toLowerCase(),
                    description: s.target_description || s.action,
                    url: s.action === 'GOTO' ? s.value : undefined,
                    target: { strategy: 'visual', value: s.target_description },
                    params: s.action === 'TYPE' ? { text: s.value } : {}
                }))
            };

            const execRes = await visualUiService.executeAdhoc({
                tc_ids: [activeCaseId],
                mode: "normal",
                parallel: false,
                dynamic_payload: [dynamicIr]
            });

            const execId = execRes.data?.execution_id;

            if (execId) {
                router.push(`/visual-ui/scenario/${execId}`);
            }
        } catch (err: any) {
            toast.error("执行启动失败 (Execution Start Failed)", { description: err.message });
        }
    };

    return (
        <div className="flex-1 flex overflow-hidden min-h-screen bg-slate-950 text-slate-200">
            {/* Left Panel: Case Explorer */}
            <div className="w-80 border-r border-slate-800 bg-slate-900 flex flex-col h-full">
                <div className="p-4 border-b border-slate-800 flex items-center justify-between">
                    <h2 className="font-semibold flex items-center gap-2 text-slate-200">
                        <Eye className="h-5 w-5 text-indigo-500" />
                        视觉UI套件 (Visual UI Suite)
                    </h2>
                    <Button size="icon" variant="ghost" onClick={handleCreateNew}>
                        <Plus className="h-4 w-4" />
                    </Button>
                </div>
                <div className="flex-1 overflow-y-auto p-2 space-y-1">
                    {isLoading ? (
                        <p className="p-4 text-center text-sm text-muted-foreground">加载中... (Loading...)</p>
                    ) : cases.length === 0 ? (
                        <p className="p-4 text-center text-sm text-muted-foreground">空空如也，快去创建吧 (Empty, create one!)</p>
                    ) : (
                        cases.map(vc => (
                            <div
                                key={vc.id}
                                onClick={() => selectCase(vc)}
                                className={`p-3 rounded-md cursor-pointer border transition-colors group ${activeCaseId === vc.id ? 'border-indigo-500 bg-indigo-500/10 text-slate-200' : 'border-transparent bg-transparent hover:bg-slate-800/50 text-slate-300'}`}
                            >
                                <div className="flex justify-between items-start">
                                    <div className="truncate font-medium text-sm">{vc.name}</div>
                                    <Trash2 className="h-4 w-4 text-rose-400 opacity-0 group-hover:opacity-100 transition-opacity hover:text-rose-500" onClick={(e) => handleDeleteClick(vc.id, e)} />
                                </div>
                                <div className="text-xs text-slate-500 mt-1 flex justify-between">
                                    <span>{vc.steps.length} 步骤 (Steps)</span>
                                    <span>{format(new Date(vc.updated_at), 'MM-dd HH:mm')}</span>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </div>

            {/* Right Panel: Canvas Editor */}
            <div className="flex-1 overflow-y-auto p-6">
                {activeCaseId ? (
                    <div className="max-w-5xl mx-auto space-y-6">
                        {/* Header Controls */}
                        <div className="flex items-center justify-between">
                            <div>
                                <h1 className="text-2xl font-bold text-slate-100">{currentName || "未命名用例 (Untitled Case)"}</h1>
                                <p className="text-slate-400 text-sm mt-1">{activeCaseId === 'NEW' ? '创建新用例草稿 (New Case Draft)' : `ID: ${activeCaseId}`}</p>
                            </div>
                            <div className="flex items-center gap-3">
                                <Button variant="outline" onClick={handleSave} disabled={isSaving} className="border-slate-700 bg-slate-900 text-slate-300 hover:bg-slate-800 hover:text-slate-100">
                                    <Save className="h-4 w-4 mr-2" />
                                    {isSaving ? "保存中... (Saving...)" : "保存用例 (Save Case)"}
                                </Button>
                                <Button onClick={handleExecute} className="bg-indigo-600 hover:bg-indigo-700 text-white">
                                    <Play className="h-4 w-4 mr-2" />
                                    运行并追踪 (Run & Track)
                                </Button>
                            </div>
                        </div>

                        {/* Meta Fields Map */}
                        {/* Meta Fields Map */}
                        <Card className="bg-slate-900 border-slate-800 shadow-xl">
                            <CardHeader className="pb-3 border-b border-slate-800">
                                <CardTitle className="text-base text-indigo-400">用例属性设定 (Case Metadata)</CardTitle>
                            </CardHeader>
                            <CardContent className="grid grid-cols-2 gap-4 pt-4">
                                <div className="space-y-1.5">
                                    <label className="text-sm font-medium text-slate-400">用例名称 (Case Name)</label>
                                    <Input value={currentName} onChange={e => setCurrentName(e.target.value)} className="bg-slate-950 border-slate-700 text-slate-100 placeholder:text-slate-500" />
                                </div>
                                <div className="space-y-1.5">
                                    <label className="text-sm font-medium text-slate-400">默认环境变量 (Base URL)</label>
                                    <Input value={currentBaseUrl} onChange={e => setCurrentBaseUrl(e.target.value)} placeholder="https://example.com" className="bg-slate-950 border-slate-700 text-slate-100 placeholder:text-slate-500" />
                                </div>
                                <div className="col-span-2 space-y-1.5">
                                    <label className="text-sm font-medium text-slate-400">用例描述 (Case Description)</label>
                                    <Input value={currentDesc} onChange={e => setCurrentDesc(e.target.value)} placeholder="记录登录/付款等业务逻辑 (e.g. Login/Payment flow)" className="bg-slate-950 border-slate-700 text-slate-100 placeholder:text-slate-500" />
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
                    <div className="h-full flex flex-col items-center justify-center text-muted-foreground">
                        <Eye className="h-16 w-16 mb-4 text-slate-700 opacity-50" />
                        <p className="text-lg">选择左侧用例或点击+开始纯视觉编排 (Select a case or click "+" to start visual orchestration)</p>
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
        </div>
    );
}
