"use client";

import React, { useState, useEffect } from 'react';
import { ShieldAlert, RefreshCw, Search, PlusCircle, AlertOctagon, TerminalSquare, BrainCircuit, Save } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { getHistoricalDefects, analyzeDefect, saveDefectAnalysis, DefectRecord, DefectAnalysisResponse } from '@/services/smartOpsService';
import { toast } from 'sonner';

export default function SmartOpsPage() {
    const [defects, setDefects] = useState<DefectRecord[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');

    // Dialog State
    const [isDialogOpen, setIsDialogOpen] = useState(false);
    const [diagInputMsg, setDiagInputMsg] = useState('');
    const [diagInputCtx, setDiagInputCtx] = useState('');
    const [analyzing, setAnalyzing] = useState(false);
    const [analysisResult, setAnalysisResult] = useState<DefectAnalysisResponse | null>(null);

    const fetchDefects = async () => {
        setLoading(true);
        try {
            const data = await getHistoricalDefects();
            setDefects(data);
        } catch (error) {
            toast.error("获取缺陷库失败", { description: String(error) });
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchDefects();
    }, []);

    const filteredDefects = defects.filter(d =>
        d.error_msg.toLowerCase().includes(searchQuery.toLowerCase()) ||
        d.root_cause.toLowerCase().includes(searchQuery.toLowerCase())
    );

    const handleAnalyze = async () => {
        if (!diagInputMsg.trim()) {
            toast.error("请输入错误信息");
            return;
        }
        setAnalyzing(true);
        setAnalysisResult(null);
        try {
            const result = await analyzeDefect({
                error_msg: diagInputMsg,
                context: diagInputCtx || undefined
            });
            setAnalysisResult(result);
            toast.success("诊断完成");
        } catch (error) {
            toast.error("AI 分析失败", { description: String(error) });
        } finally {
            setAnalyzing(false);
        }
    };

    const handleSaveToPool = async () => {
        if (!analysisResult) return;

        try {
            await saveDefectAnalysis({
                error_msg: diagInputMsg,
                root_cause: analysisResult.analysis.root_cause,
                suggested_fix: analysisResult.analysis.suggested_fix
            });
            toast.success("已成功收录至缺陷池与向量库");
            setIsDialogOpen(false);
            fetchDefects(); // Refresh background
        } catch (error) {
            toast.error("收录失败", { description: String(error) });
        }
    };

    return (
        <div className="flex-1 overflow-auto p-6 space-y-6 text-slate-900">
            {/* Header */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h1 className="text-3xl font-bold bg-gradient-to-r from-sky-600 via-blue-600 to-violet-600 bg-clip-text text-transparent flex items-center gap-2">
                        <ShieldAlert className="w-8 h-8 text-sky-600" />
                        智能运维 (Smart Ops)
                    </h1>
                    <p className="text-slate-600 mt-2">
                        AI 分布式缺陷诊断与兜底系统。自动寻根、特征向量检索，告别重复排查。
                    </p>
                </div>
                <div className="flex gap-3">
                    <Button variant="outline" className="border-sky-200 bg-white/80 text-slate-700 shadow-sm hover:bg-sky-50 hover:text-sky-800" onClick={fetchDefects}>
                        <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                        刷新缺陷池
                    </Button>
                    <Button className="bg-gradient-to-r from-sky-500 via-blue-500 to-violet-500 text-white shadow-lg shadow-sky-500/25 hover:from-sky-600 hover:via-blue-600 hover:to-violet-600" onClick={() => {
                        setIsDialogOpen(true);
                        setAnalysisResult(null);
                        setDiagInputMsg('');
                        setDiagInputCtx('');
                    }}>
                        <PlusCircle className="w-4 h-4 mr-2" />
                        手动诊断报错
                    </Button>
                </div>
            </div>

            {/* Content Body */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

                {/* Defect Pool (Left 2/3) */}
                <div className="lg:col-span-2 space-y-6">
                    <Card className="rounded-2xl border-white/70 bg-white/80 shadow-[0_20px_60px_-35px_rgba(14,165,233,0.35)] backdrop-blur-xl">
                        <CardHeader className="border-b border-sky-100 pb-4">
                            <div className="flex justify-between items-center">
                                <CardTitle className="text-lg font-bold flex items-center gap-2">
                                    <AlertOctagon className="w-5 h-5 text-rose-400" />
                                    缺陷追溯池 (Defect Pool)
                                </CardTitle>
                                <div className="relative w-64">
                                    <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-slate-500" />
                                    <Input
                                        placeholder="搜索错误信息..."
                                        className="pl-9 bg-white/85 border-sky-200 text-slate-900 placeholder:text-slate-600 h-9 shadow-sm"
                                        value={searchQuery}
                                        onChange={(e) => setSearchQuery(e.target.value)}
                                    />
                                </div>
                            </div>
                            <CardDescription className="text-slate-600 mt-1">
                                已收录至 Milvus 的历史缺陷及其 AI 分析报告
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="pt-6">
                            {loading ? (
                                <div className="flex justify-center items-center py-12 text-slate-500">
                                    <RefreshCw className="w-6 h-6 animate-spin mr-2" />
                                    加载数据中...
                                </div>
                            ) : filteredDefects.length === 0 ? (
                                <div className="flex flex-col items-center justify-center py-16 text-slate-500 text-center border border-dashed border-sky-200 rounded-2xl bg-sky-50/50">
                                    <ShieldAlert className="w-12 h-12 text-sky-300 mb-4" />
                                    <h3 className="text-lg font-medium text-slate-800">暂无匹配缺陷</h3>
                                    <p className="mt-1 max-w-sm text-sm">当测试用例执行遭遇失败后，系统将使用 AI 自动分析根因并存入此处。</p>
                                </div>
                            ) : (
                                <div className="space-y-4">
                                    {filteredDefects.map((defect) => (
                                        <div key={defect.id} className="rounded-2xl border border-sky-100 bg-white/75 p-4 grid grid-cols-1 md:grid-cols-2 gap-4 shadow-sm">
                                            <div>
                                                <div className="flex items-center gap-2 mb-2">
                                                    <TerminalSquare className="w-4 h-4 text-rose-400" />
                                                    <h4 className="font-semibold text-rose-700">原始错误 (Error)</h4>
                                                </div>
                                                <div className="bg-slate-900 border border-slate-800 p-2 rounded text-xs font-mono text-rose-300 break-words h-24 overflow-y-auto">
                                                    {defect.error_msg}
                                                </div>
                                            </div>
                                            <div className="space-y-3">
                                                <div>
                                                    <h4 className="font-semibold text-sky-700 text-sm mb-1 flex items-center gap-1">
                                                        <Search className="w-3.5 h-3.5" /> 根因分析 (Root Cause)
                                                    </h4>
                                                    <p className="text-slate-700 text-sm">{defect.root_cause}</p>
                                                </div>
                                                <div>
                                                    <h4 className="font-semibold text-emerald-700 text-sm mb-1 flex items-center gap-1">
                                                        <PlusCircle className="w-3.5 h-3.5" /> 修复建议 (Fix)
                                                    </h4>
                                                    <p className="text-slate-700 text-sm">{defect.suggested_fix}</p>
                                                </div>
                                                <div className="text-xs text-slate-500 text-right">
                                                    收录时间: {new Date(defect.created_at).toLocaleString()} | ID: {defect.id}
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </div>

                {/* Status & Milvus Stats (Right 1/3) */}
                <div className="space-y-6">
                    <Card className="rounded-2xl border-white/70 bg-white/80 shadow-[0_20px_60px_-35px_rgba(14,165,233,0.35)] backdrop-blur-xl">
                        <CardHeader>
                            <CardTitle className="text-lg font-bold">知识库状态</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="flex justify-between items-center p-3 rounded-md bg-sky-50/70 border border-sky-100">
                                <span className="text-slate-600 text-sm">运行状态</span>
                                <div className="flex items-center gap-2">
                                    <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                                    <span className="text-emerald-700 font-bold text-sm">在线 (Online)</span>
                                </div>
                            </div>

                            <div className="flex justify-between items-center p-3 rounded-md bg-sky-50/70 border border-sky-100">
                                <span className="text-slate-600 text-sm">Milvus 集合</span>
                                <span className="text-slate-700 font-mono text-xs">defect_knowledge_base</span>
                            </div>

                            <div className="flex justify-between items-center p-3 rounded-md bg-sky-50/70 border border-sky-100">
                                <span className="text-slate-600 text-sm">已存缺陷数</span>
                                <span className="text-sky-700 font-bold">{defects.length} 条</span>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            </div>

            {/* Manual Diagnosis Dialog */}
            <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
                <DialogContent className="sm:max-w-[700px] border-slate-200 bg-white text-slate-900 shadow-2xl">
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2 text-xl font-bold bg-gradient-to-r from-sky-600 via-blue-600 to-violet-600 bg-clip-text text-transparent">
                            <BrainCircuit className="w-6 h-6 text-sky-600" />
                            AI 手动根因诊断 (Defect Analysis)
                        </DialogTitle>
                        <DialogDescription className="text-slate-600">
                            粘贴测试日志或异常堆栈，调用大模型分析失败原因，并自动在 Milvus 中检索相似历史错误。
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-slate-700">原始错误日志 (Error Log) *</label>
                            <Textarea
                                placeholder="Paste the stack trace or error message here..."
                                className="bg-[#0D1117] border-slate-800 h-32 font-mono text-xs text-slate-200 placeholder:text-slate-500"
                                value={diagInputMsg}
                                onChange={(e) => setDiagInputMsg(e.target.value)}
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-slate-700">上下文补充 (Context) - 可选</label>
                            <Textarea
                                placeholder="Any additional context like DOM state, steps leading to the error..."
                                className="bg-white/85 border-sky-200 h-16 text-slate-900 placeholder:text-slate-400 shadow-sm"
                                value={diagInputCtx}
                                onChange={(e) => setDiagInputCtx(e.target.value)}
                            />
                        </div>

                        {/* Results Box */}
                        {analyzing && (
                            <div className="flex justify-center items-center py-6 text-sky-600">
                                <BrainCircuit className="w-6 h-6 animate-pulse mr-2" />
                                AI 大模型正在深度思考中... (Thinking)
                            </div>
                        )}

                        {analysisResult && (
                            <div className="mt-4 p-4 border border-sky-100 bg-sky-50/70 rounded-2xl space-y-4">
                                <h3 className="font-bold text-sky-700 flex items-center gap-2">
                                    <ShieldAlert className="w-5 h-5" />
                                    诊断结果报告
                                </h3>
                                <div>
                                    <h4 className="font-semibold text-rose-700 text-sm mb-1">推测根因</h4>
                                    <p className="text-slate-700 text-sm whitespace-pre-wrap">{analysisResult.analysis.root_cause}</p>
                                </div>
                                <div className="mt-3">
                                    <h4 className="font-semibold text-emerald-700 text-sm mb-1">修复建议</h4>
                                    <p className="text-slate-700 text-sm whitespace-pre-wrap">{analysisResult.analysis.suggested_fix}</p>
                                </div>

                                {analysisResult.similar_defects?.length > 0 && (
                                    <div className="mt-4 pt-4 border-t border-sky-100">
                                        <h4 className="font-semibold text-amber-700 text-sm mb-2">发现相似历史缺陷 (MILVUS Search)</h4>
                                        <ul className="space-y-2">
                                            {analysisResult.similar_defects.map((sd, idx) => {
                                                const score = (sd as Record<string, unknown>).score as number | undefined;
                                                const solution = (sd as Record<string, unknown>).solution as string | undefined;
                                                return (
                                                    <li key={idx} className="bg-white/80 p-2 rounded-xl border border-sky-100 text-xs shadow-sm">
                                                        <span className="text-rose-700 line-clamp-1">{sd.error_msg}</span>
                                                        <span className="text-slate-600 line-clamp-1 mt-1">-&gt; {solution || sd.suggested_fix} (Score: {score?.toFixed(3) ?? '-'})</span>
                                                    </li>
                                                );
                                            })}
                                        </ul>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>

                    <DialogFooter>
                        {analysisResult ? (
                            <div className="flex w-full justify-between items-center">
                                <span className="text-xs text-slate-500">
                                    对结果满意？将其收录至知识库可避免团队重复踩坑。
                                </span>
                                <div className="flex gap-2">
                                    <Button variant="secondary" onClick={() => setIsDialogOpen(false)}>关闭</Button>
                                    <Button className="bg-emerald-600 text-white shadow-lg shadow-emerald-500/25 hover:bg-emerald-700" onClick={handleSaveToPool}>
                                        <Save className="w-4 h-4 mr-2" />
                                        确认并收录至缺陷池
                                    </Button>
                                </div>
                            </div>
                        ) : (
                            <Button className="w-full bg-gradient-to-r from-sky-500 via-blue-500 to-violet-500 text-white shadow-lg shadow-sky-500/25 hover:from-sky-600 hover:via-blue-600 hover:to-violet-600" onClick={handleAnalyze} disabled={analyzing || !diagInputMsg}>
                                {analyzing ? '诊断中...' : '提交 AI 分析 (Analyze)'}
                            </Button>
                        )}
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}
