"use client"

import React, { useState, useEffect } from 'react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, Trash2, Code2, Save, PlayCircle, AlertCircle } from "lucide-react";
import { toast } from "sonner";
import { format } from "date-fns";

import { apiAutoService, ApiTestCase, ApiStep, ChainExecutionResult } from '@/services/apiAutoService';
import { RequestBuilder } from '@/components/api-auto/RequestBuilder';
import { ResponseConsole } from '@/components/api-auto/ResponseConsole';
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
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { getEnvironments, Environment } from '@/services/environmentService';

const NEW_STEP_TEMPLATE: ApiStep = {
    id: "step_1",
    name: "Request 1",
    request: {
        method: "GET",
        url: "https://jsonplaceholder.typicode.com/todos/1",
        headers: {
            "Accept": "application/json"
        },
        query_params: {},
        timeout_ms: 10000
    },
    extraction: {},
    assertion: {
        status_code: 200,
        json_assertions: {}
    }
};

export default function ApiAutoPage() {
    const [cases, setCases] = useState<ApiTestCase[]>([]);
    const [activeCase, setActiveCase] = useState<ApiTestCase | null>(null);
    const [isLoadingList, setIsLoadingList] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [isExecuting, setIsExecuting] = useState(false);

    // Console State
    const [execResult, setExecResult] = useState<ChainExecutionResult | null>(null);

    const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
    const [caseToDelete, setCaseToDelete] = useState<string | null>(null);

    const [environments, setEnvironments] = useState<Environment[]>([]);
    const [selectedEnv, setSelectedEnv] = useState<string>("default");

    useEffect(() => {
        loadCases();
        loadEnvironments();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const loadEnvironments = async () => {
        try {
            const data = await getEnvironments(true);
            setEnvironments(data);
        } catch (err) {
            console.error("Failed to load environments", err);
        }
    };

    const loadCases = async () => {
        setIsLoadingList(true);
        try {
            const res = await apiAutoService.getCases();
            setCases(res.data.items || []);
            // Pre-select first item if exists and no active case
            if (res.data.items?.length > 0 && !activeCase) {
                setActiveCase(res.data.items[0]);
            }
        } catch (err: unknown) {
            const error = err as { message?: string };
            if (!error?.message?.includes("Failed to fetch")) {
                toast.error("加载接口用例失败 (Failed to load API cases)", { description: error.message });
            }
        } finally {
            setIsLoadingList(false);
        }
    };

    const handleCreateNew = () => {
        const newCase: ApiTestCase = {
            id: "NEW", // Marker for unsaved
            name: "未命名接口集合 (Untitled API Collection)",
            description: "",
            mode: "API",
            priority: "P1",
            status: "active",
            tags: [],
            steps: [{ ...NEW_STEP_TEMPLATE }] // Deep copy to prevent ref sharing if created multiple times
        };
        setActiveCase(newCase);
        setExecResult(null); // Clear console
    };

    const handleSave = async () => {
        if (!activeCase) return;
        setIsSaving(true);
        try {
            let savedCase;
            if (activeCase.id === "NEW") {
                const { id: _id, ...payload } = activeCase;
                const res = await apiAutoService.createCase(payload);
                savedCase = res.data;
                toast.success("新建成功 (Created)");
            } else {
                const res = await apiAutoService.updateCase(activeCase.id!, activeCase);
                savedCase = res.data;
                toast.success("保存成功 (Saved)");
            }
            setActiveCase(savedCase);
            await loadCases();
        } catch (err: unknown) {
            toast.error("保存失败 (Save Failed)", { description: (err as { message?: string }).message });
        } finally {
            setIsSaving(false);
        }
    };

    const handleDeleteClick = (id: string, e: React.MouseEvent) => {
        e.stopPropagation();
        setCaseToDelete(id);
        setDeleteConfirmOpen(true);
    };

    const confirmDelete = async () => {
        if (!caseToDelete) return;
        try {
            await apiAutoService.deleteCase(caseToDelete);
            toast.success("已删除 (Deleted)");
            if (activeCase?.id === caseToDelete) setActiveCase(null);
            loadCases();
        } catch (err: unknown) {
            toast.error("删除失败 (Delete Failed)", { description: (err as { message?: string }).message });
        } finally {
            setDeleteConfirmOpen(false);
            setCaseToDelete(null);
        }
    };

    const handleRunChain = async () => {
        if (!activeCase || activeCase.steps.length === 0) {
            toast.error("没有可执行的请求 (No executable requests)");
            return;
        }

        setIsExecuting(true);
        setExecResult(null);

        try {
            const envId = selectedEnv === "default" ? undefined : selectedEnv;
            const res = await apiAutoService.runApiChain(activeCase.steps, "", {}, {}, envId);
            setExecResult(res.data);
            if (res.data.success) {
                toast.success("执行完成: 全通过 (Execution Complete: All Passed)");
            } else {
                toast.error(`执行完成: ${res.data.failed_steps}个失败 (Execution Complete: ${res.data.failed_steps} Failed)`);
            }
        } catch (err: unknown) {
            toast.error("执行接口失败 (API Execution Failed)", { description: (err as { message?: string }).message });
        } finally {
            setIsExecuting(false);
        }
    };

    const updateActiveCaseField = (field: keyof ApiTestCase, value: ApiTestCase[keyof ApiTestCase]) => {
        if (!activeCase) return;
        setActiveCase({ ...activeCase, [field]: value });
    };

    const updateStep = (index: number, newStep: ApiStep) => {
        if (!activeCase) return;
        const newSteps = [...activeCase.steps];
        newSteps[index] = newStep;
        setActiveCase({ ...activeCase, steps: newSteps });
    };

    return (
        <div className="flex h-[calc(100vh-4rem)] overflow-hidden text-slate-900">
            {/* Left Panel: API Case Library */}
            <div className="w-80 shrink-0 flex flex-col h-full rounded-3xl border border-white/70 bg-white/75 shadow-[12px_0_40px_-28px_rgba(14,165,233,0.5)] backdrop-blur-xl overflow-hidden">
                <div className="p-4 border-b border-sky-100 flex items-center justify-between">
                    <h2 className="font-semibold flex items-center gap-2 text-slate-900">
                        <Code2 className="h-5 w-5 text-violet-600" />
                        API接口工厂 (API Factory)
                    </h2>
                    <Button size="icon" variant="ghost" onClick={handleCreateNew}>
                        <Plus className="h-4 w-4" />
                    </Button>
                </div>
                <div className="flex-1 overflow-y-auto p-2 space-y-1">
                    {isLoadingList ? (
                        <p className="p-4 text-center text-sm text-muted-foreground">加载中... (Loading...)</p>
                    ) : cases.length === 0 ? (
                        <p className="p-4 text-center text-sm text-muted-foreground">空空如也，快去创建吧 (Empty, create one!)</p>
                    ) : (
                        cases.map(tc => (
                            <div
                                key={tc.id}
                                onClick={() => { setActiveCase(tc); setExecResult(null); }}
                                className={`p-3 rounded-2xl cursor-pointer border transition-all group ${activeCase?.id === tc.id ? 'border-sky-300 bg-gradient-to-r from-sky-100 via-white to-violet-100 text-slate-950 shadow-sm ring-1 ring-sky-200' : 'border-transparent bg-white/20 text-slate-700 hover:border-sky-200 hover:bg-white/80 hover:shadow-sm'}`}
                            >
                                <div className="flex justify-between items-start">
                                    <div className="truncate font-medium text-sm">{tc.name}</div>
                                    <Trash2 className="h-4 w-4 text-rose-400 opacity-0 group-hover:opacity-100 transition-opacity hover:text-rose-500" onClick={(e) => handleDeleteClick(tc.id!, e)} />
                                </div>
                                <div className="text-xs text-slate-500 mt-1 flex justify-between">
                                    <span>{tc.steps?.length || 0} Req</span>
                                    <span>{tc.updated_at ? format(new Date(tc.updated_at), 'MM-dd HH:mm') : 'New'}</span>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </div>

            {/* Right Panel: API Workbench */}
            <div className="flex-1 flex flex-col h-full overflow-y-auto">
                {activeCase ? (
                    <div className="p-6 max-w-6xl w-full mx-auto space-y-6">
                        {/* Workbench Header */}
                        <div className="flex items-center justify-between">
                            <div className="flex-1 max-w-xl">
                                <Input
                                    className="text-2xl font-bold bg-transparent border-0 border-b border-transparent focus-visible:ring-0 focus-visible:border-sky-400 h-10 px-0 shadow-none rounded-none text-slate-950 placeholder:text-slate-400"
                                    value={activeCase.name}
                                    onChange={(e) => updateActiveCaseField("name", e.target.value)}
                                    placeholder="集合名称 (Collection Name)"
                                />
                                <Input
                                    className="text-sm text-slate-600 bg-transparent border-0 h-7 px-0 shadow-none focus-visible:ring-0 mt-1 placeholder:text-slate-400"
                                    value={activeCase.description || ""}
                                    onChange={(e) => updateActiveCaseField("description", e.target.value)}
                                    placeholder="添加关于此集合的业务描述... (Add business description...)"
                                />
                            </div>
                            <div className="flex items-center gap-3">
                                <Select value={selectedEnv} onValueChange={setSelectedEnv}>
                                    <SelectTrigger className="w-48 bg-white/80 border-sky-200 text-slate-800 h-9 text-sm shadow-sm">
                                        <SelectValue placeholder="选择运行环境" />
                                    </SelectTrigger>
                                    <SelectContent className="bg-white border-sky-100 text-slate-800 shadow-xl">
                                        <SelectItem value="default">无环境设定 (No Env)</SelectItem>
                                        {environments.map(env => (
                                            <SelectItem key={env.id} value={env.id}>
                                                {env.name}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>

                                <Button variant="outline" size="sm" onClick={handleSave} disabled={isSaving} className="border-sky-200 bg-white/80 text-slate-700 shadow-sm hover:bg-sky-50 hover:text-sky-800">
                                    <Save className="h-4 w-4 mr-2" />
                                    {isSaving ? "保存中" : "保存"}
                                </Button>
                                {/* Only allow chain execution if we have steps */}
                                {activeCase.steps.length > 0 && (
                                    <Button size="sm" onClick={handleRunChain} disabled={isExecuting} className="bg-gradient-to-r from-sky-500 via-blue-500 to-violet-500 text-white shadow-lg shadow-sky-500/25 hover:from-sky-600 hover:via-blue-600 hover:to-violet-600">
                                        <PlayCircle className="h-4 w-4 mr-2" />
                                        运行 ({activeCase.steps.length})
                                    </Button>
                                )}
                            </div>
                        </div>

                        {/* Request Map (For MVP, just show the first step as the main request builder. 
                            In a full Postman, we'd have a sidebar inside the workbench to select steps. 
                            Let's map through steps for now sequentially as cards) */}
                        <div className="space-y-8">
                            {activeCase.steps.map((step, index) => (
                                <div key={index} className="space-y-2">
                                    <div className="flex items-center justify-between px-1">
                                        <h3 className="font-semibold text-slate-800 flex items-center gap-2">
                                            <span className="bg-sky-50 text-sky-700 border border-sky-100 text-xs px-2 py-0.5 rounded-full">步骤 (Step) {index + 1}</span>
                                            {step.name}
                                        </h3>
                                    </div>
                                    {((step as unknown as { step_type?: string }).step_type === "UI" || !step.request) ? (
                                        <div className="p-4 rounded-2xl border border-amber-200 bg-amber-50/80 text-slate-700 flex flex-col gap-2 shadow-sm">
                                            <div className="flex items-center text-amber-500 text-sm">
                                                <AlertCircle className="w-4 h-4 mr-2" />
                                                包含了非 API 类型的步骤 (UI/混合步骤)
                                            </div>
                                            <div className="text-sm">
                                                描述 (Description): {(step as unknown as { description?: string }).description || "无"}
                                            </div>
                                            <div className="text-sm">
                                                目前 API 工作台仅支持可视化编排 HTTP 接口测试步骤。
                                            </div>
                                        </div>
                                    ) : (
                                        <RequestBuilder
                                            step={step}
                                            onChange={(newStep) => updateStep(index, newStep)}
                                            onRun={handleRunChain}
                                            isExecuting={isExecuting}
                                        />
                                    )}
                                </div>
                            ))}
                        </div>

                        {/* Console Panel */}
                        <ResponseConsole result={execResult} isLoading={isExecuting} />

                    </div>
                ) : (
                    <div className="h-full flex flex-col items-center justify-center text-slate-500">
                        <Code2 className="h-16 w-16 mb-4 text-sky-300" />
                        <p className="text-lg">选择左侧用例，进入API自动化工作区 (Select a case to enter the API workbench)</p>
                    </div>
                )}
            </div>

            <AlertDialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
                <AlertDialogContent className="border-slate-200 bg-white text-slate-900 shadow-2xl">
                    <AlertDialogHeader>
                        <AlertDialogTitle>确定删除此API用例吗？ (Delete this API case?)</AlertDialogTitle>
                        <AlertDialogDescription className="text-slate-600">
                            此操作不可逆，将永久删除。 (This action is irreversible and permanent.)
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel className="border-sky-200 bg-white text-slate-700 hover:bg-sky-50 hover:text-sky-800">取消 (Cancel)</AlertDialogCancel>
                        <AlertDialogAction onClick={confirmDelete} className="bg-rose-600 hover:bg-rose-700 text-white border-none">
                            确定删除 (Confirm Delete)
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    );
}
