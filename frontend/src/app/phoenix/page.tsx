"use client";

import React, { useEffect, useState } from "react";
import {
    Flame, Code2, GitCommit, GitBranch, History, BookOpen
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import {
    ScriptInfo, VersionInfo, getScripts, getScriptCode, getScriptHistory
} from "@/services/phoenixService";

export default function PhoenixPage() {
    const [scripts, setScripts] = useState<ScriptInfo[]>([]);
    const [selectedScript, setSelectedScript] = useState<ScriptInfo | null>(null);
    const [code, setCode] = useState<string>("");
    const [history, setHistory] = useState<VersionInfo[]>([]);
    const [activeTab, setActiveTab] = useState<'code' | 'history'>('code');
    const [loading, setLoading] = useState(false);

    const fetchScripts = async () => {
        try {
            const data = await getScripts(0, 50);
            setScripts(data);
            if (data.length > 0 && !selectedScript) {
                handleSelectScript(data[0]);
            }
        } catch (_error) {
            toast.error("获取脚本列表失败");
        }
    };

    useEffect(() => {
        fetchScripts();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const handleSelectScript = async (script: ScriptInfo) => {
        setSelectedScript(script);
        setLoading(true);
        setActiveTab('code');
        try {
            const codeRes = await getScriptCode(script.script_id);
            setCode(codeRes.code);
            const histRes = await getScriptHistory(script.script_id);
            setHistory(histRes);
        } catch (_error) {
            toast.error("获取脚本详情失败");
            setCode("未找到或加载失败");
            setHistory([]);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex h-[calc(100vh-2rem)] overflow-hidden text-slate-900 -m-4">
            {/* 左侧菜单 - 脚本仓库 */}
            <div className="w-80 flex flex-col rounded-3xl border border-white/70 bg-white/75 shadow-[12px_0_40px_-28px_rgba(244,63,94,0.35)] backdrop-blur-xl overflow-hidden">
                <div className="p-4 border-b border-rose-100 flex justify-between items-center">
                    <div>
                        <h2 className="text-lg font-bold flex items-center gap-2 text-rose-700">
                            <Flame className="w-5 h-5" /> 凤凰仓库
                        </h2>
                        <span className="text-xs text-slate-500">Phoenix Nirvana Vault</span>
                    </div>
                    <Badge variant="outline" className="border-amber-200 bg-amber-50 text-amber-700">
                        实验功能
                    </Badge>
                </div>

                <div className="flex-1 overflow-y-auto p-2 space-y-2">
                    {scripts.length === 0 ? (
                        <div className="text-center p-8 text-slate-500 text-sm">
                            <Code2 className="w-8 h-8 mx-auto mb-2 opacity-20" />
                            <p>暂无编译脚本</p>
                        </div>
                    ) : null}

                    {scripts.map(s => (
                        <div
                            key={s.script_id}
                            onClick={() => handleSelectScript(s)}
                            className={`p-3 rounded-2xl cursor-pointer border transition-all ${selectedScript?.script_id === s.script_id
                                    ? 'bg-gradient-to-r from-rose-50 via-white to-amber-50 border-rose-300 shadow-sm ring-1 ring-rose-200'
                                    : 'bg-white/30 border-transparent hover:border-rose-200 hover:bg-white/85 hover:shadow-sm'
                                }`}
                        >
                            <div className="font-medium text-slate-900 line-clamp-1">{s.name}</div>
                            <div className="flex justify-between items-center mt-2 text-xs text-slate-500">
                                <span className="flex items-center gap-1 font-mono"><Code2 className="w-3 h-3" /> {s.script_id.substring(0, 10)}</span>
                                <span>{new Date(s.created_at).toLocaleDateString()}</span>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* 右侧主区域 */}
            <div className="flex-1 flex flex-col overflow-hidden">
                {selectedScript ? (
                    <>
                        <div className="p-6 border-b border-rose-100 bg-white/70 backdrop-blur-xl">
                            <div className="flex justify-between items-start">
                                <div>
                                    <h1 className="text-2xl font-bold text-slate-950 flex items-center gap-3">
                                        {selectedScript.name}
                                        <Badge variant="outline" className="border-rose-200 text-rose-700 bg-rose-50">
                                            {selectedScript.strategy} Mode
                                        </Badge>
                                    </h1>
                                    <p className="text-sm text-slate-600 mt-2 font-mono bg-rose-50 p-1.5 px-3 rounded-md inline-flex items-center gap-2 border border-rose-100">
                                        <GitBranch className="w-3 h-3" /> {selectedScript.file_path}
                                    </p>
                                </div>
                                <Badge variant="outline" className="border-amber-200 bg-amber-50 text-amber-700">
                                    脚本固化预览
                                </Badge>
                            </div>

                            {/* Tabs */}
                            <div className="flex gap-6 mt-8 border-b border-rose-100">
                                <button
                                    onClick={() => setActiveTab('code')}
                                    className={`pb-3 text-sm font-medium transition-colors relative ${activeTab === 'code' ? 'text-rose-700' : 'text-slate-500 hover:text-slate-800'}`}
                                >
                                    <div className="flex items-center gap-2"><Code2 className="w-4 h-4" /> 源代码预览</div>
                                    {activeTab === 'code' && <div className="absolute bottom-0 left-0 w-full h-[2px] bg-rose-500 rounded-t-full" />}
                                </button>
                                <button
                                    onClick={() => setActiveTab('history')}
                                    className={`pb-3 text-sm font-medium transition-colors relative ${activeTab === 'history' ? 'text-rose-700' : 'text-slate-500 hover:text-slate-800'}`}
                                >
                                    <div className="flex items-center gap-2"><History className="w-4 h-4" /> 版本与分支历史</div>
                                    {activeTab === 'history' && <div className="absolute bottom-0 left-0 w-full h-[2px] bg-rose-500 rounded-t-full" />}
                                </button>
                            </div>
                        </div>

                        <div className="flex-1 overflow-auto p-6">
                            {loading ? (
                                <div className="animate-pulse space-y-4">
                                    <div className="h-4 bg-rose-100 rounded w-1/4"></div>
                                    <div className="h-4 bg-rose-100 rounded w-1/2"></div>
                                    <div className="h-20 bg-rose-100 rounded"></div>
                                </div>
                            ) : (
                                <>
                                    {/* Code Tab */}
                                    {activeTab === 'code' && (
                                        <div className="flex flex-col h-full rounded-lg border border-slate-800 overflow-hidden bg-[#1e1e1e]">
                                            <div className="bg-slate-900 border-b border-slate-800 px-4 py-2 flex items-center justify-between text-xs text-slate-400 font-mono">
                                                <span>{selectedScript.file_path}</span>
                                                <span>Language: Python (Pytest)</span>
                                            </div>
                                            <pre className="p-4 text-sm font-mono overflow-auto text-emerald-300">
                                                <code>{code}</code>
                                            </pre>
                                        </div>
                                    )}

                                    {/* History Tab */}
                                    {activeTab === 'history' && (
                                        <div className="space-y-4 max-w-4xl mx-auto">
                                            {history.length === 0 ? (
                                                <div className="text-center p-8 text-slate-500 bg-white/70 rounded-2xl border border-rose-100 shadow-sm">
                                                    暂无 Git 提交记录
                                                </div>
                                            ) : (
                                                <div className="relative border-l-2 border-rose-100 pl-6 ml-4 space-y-8">
                                                    {history.map((commit) => (
                                                        <div key={commit.version} className="relative">
                                                            <div className="absolute -left-[35px] top-1 p-1 bg-white border-2 border-rose-400 rounded-full shadow-sm">
                                                                <GitCommit className="w-4 h-4 text-rose-500" />
                                                            </div>
                                                            <div className="bg-white/80 border border-rose-100 p-4 rounded-2xl shadow-sm">
                                                                <h4 className="font-semibold text-slate-900">{commit.message}</h4>
                                                                <div className="flex flex-wrap items-center gap-4 mt-3 text-xs text-slate-400 font-mono">
                                                                    <span className="bg-rose-50 border border-rose-100 px-2 py-1 rounded text-rose-700">Commit: {commit.version}</span>
                                                                    <span>Author: {commit.author}</span>
                                                                    <span>Time: {new Date(commit.date).toLocaleString()}</span>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </>
                            )}
                        </div>
                    </>
                ) : (
                    <div className="flex-1 flex flex-col items-center justify-center text-slate-500">
                        <BookOpen className="w-16 h-16 mb-4 opacity-20" />
                        <h2 className="text-xl font-medium mb-2">欢迎来到凤凰涅槃层</h2>
                        <p className="text-sm max-w-md text-center">从左侧选择一个脚本进行代码查阅、Git 分支分析或是异常自愈处理。</p>
                        <p className="mt-4 text-xs text-slate-400">脚本固化能力已降级为实验预览，请从真实执行结果或后续 Trace 入口生成脚本。</p>
                    </div>
                )}
            </div>
        </div>
    );
}
