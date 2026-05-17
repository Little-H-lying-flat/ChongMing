"use client";

import React, { useEffect, useState } from "react";
import {
    Flame, Code2, GitCommit, GitBranch, History, PlayCircle, Plus, BookOpen, Bug, Activity
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import {
    ScriptInfo, VersionInfo, getScripts, getScriptCode, getScriptHistory, compileTrace
} from "@/services/phoenixService";

export default function PhoenixPage() {
    const [scripts, setScripts] = useState<ScriptInfo[]>([]);
    const [selectedScript, setSelectedScript] = useState<ScriptInfo | null>(null);
    const [code, setCode] = useState<string>("");
    const [history, setHistory] = useState<VersionInfo[]>([]);
    const [activeTab, setActiveTab] = useState<'code' | 'history' | 'heal'>('code');
    const [loading, setLoading] = useState(false);
    const [compiling, setCompiling] = useState(false);

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

    const handleMockCompile = async () => {
        setCompiling(true);
        const toastId = toast.loading("正在利用大模型编译执行轨迹为 Pytest 脚本...");

        try {
            // Mock trace payload similar to what RightPupil would produce
            const mockTrace = {
                trace_id: `TRACE_${Date.now()}`,
                trace_data: {
                    name: "User Login Flow Trace",
                    scenario_id: "TC-001",
                    actions: [
                        { type: "navigate", target: "https://example.com/login", description: "Open Login Page" },
                        { type: "click", target: "#username", description: "Click Username Field" },
                        { type: "input", target: "#username", value: "testuser", description: "Type Username" },
                        { type: "click", target: "#password", description: "Click Password Field" },
                        { type: "input", target: "#password", value: "password123", description: "Type Password" },
                        { type: "click", target: ".submit-btn", description: "Click Login Button" },
                        { type: "assert", target: ".welcome-msg", value: "Welcome", description: "Verify Login Success" }
                    ]
                }
            };

            await compileTrace(mockTrace);
            toast.success("轨迹编译成功！", { id: toastId });
            await fetchScripts();
        } catch (_error) {
            toast.error("编译失败", { id: toastId });
        } finally {
            setCompiling(false);
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
                    <Button variant="outline" size="icon" onClick={handleMockCompile} disabled={compiling} className="border-rose-200 bg-white/80 text-rose-700 shadow-sm hover:bg-rose-50 hover:text-rose-800" title="模拟轨迹编译 (Mock Trace Compile)">
                        {compiling ? <Activity className="w-4 h-4 animate-spin text-rose-400" /> : <Plus className="w-4 h-4" />}
                    </Button>
                </div>

                <div className="flex-1 overflow-y-auto p-2 space-y-2">
                    {scripts.length === 0 && !compiling ? (
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
                                <div className="flex gap-2">
                                    <Button variant="outline" className="border-emerald-200 text-emerald-700 bg-emerald-50 hover:bg-emerald-100 hover:text-emerald-800">
                                        <PlayCircle className="w-4 h-4 mr-2" /> 执行脚本
                                    </Button>
                                </div>
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
                                <button
                                    onClick={() => setActiveTab('heal')}
                                    className={`pb-3 text-sm font-medium transition-colors relative ${activeTab === 'heal' ? 'text-rose-700' : 'text-slate-500 hover:text-slate-800'}`}
                                >
                                    <div className="flex items-center gap-2"><Bug className="w-4 h-4" /> 自愈修复模拟器</div>
                                    {activeTab === 'heal' && <div className="absolute bottom-0 left-0 w-full h-[2px] bg-rose-500 rounded-t-full" />}
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

                                    {/* Heal Tab (Mock view) */}
                                    {activeTab === 'heal' && (
                                        <div className="max-w-2xl mx-auto mt-8 text-center text-slate-600 space-y-4">
                                            <Bug className="w-16 h-16 mx-auto opacity-20" />
                                            <h3 className="text-xl font-bold text-slate-900">异常堆栈自愈修复</h3>
                                            <p className="text-sm">当执行发生异常退出时，凤凰涅槃层会自动分析抛出的 Traceback 与报错上下文，重写对应的元素定位策略并进行代码固化。</p>
                                            <p className="text-sm bg-slate-900/50 p-4 border border-rose-500/20 text-rose-300 rounded-lg inline-block text-left relative">
                                                <code>
                                                    waiting for selector &quot;.submit-btn&quot; to be visible<br />
                                                    TimeoutError: page.waitForSelector: Timeout 10000ms exceeded.
                                                </code>
                                            </p>
                                            <div className="pt-4">
                                                <Button disabled variant="outline" className="border-rose-200 text-rose-700 bg-rose-50">
                                                    模块对接中 (Module Integrating)
                                                </Button>
                                            </div>
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
                        <Button onClick={handleMockCompile} disabled={compiling} className="mt-8 bg-gradient-to-r from-rose-500 via-orange-500 to-amber-500 text-white shadow-lg shadow-rose-500/25 hover:from-rose-600 hover:via-orange-600 hover:to-amber-600">
                            {compiling ? "编译中..." : "产生一条 Mock 轨迹进行编译测试"}
                        </Button>
                    </div>
                )}
            </div>
        </div>
    );
}
