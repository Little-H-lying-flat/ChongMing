"use client";

import { useState, useEffect, useRef } from "react";
import { AreaChart, Area, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer } from "recharts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Activity, Play, Square, Users, Zap, Clock, AlertTriangle, Target } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { turboService } from "@/services/turboService";

export default function PerformancePage() {
  const [testCases, setTestCases] = useState<{ id: string; name: string; method?: string; url?: string; target_host?: string }[]>([]);
  const [selectedCase, setSelectedCase] = useState<{ id: string; name: string; method?: string; url?: string; target_host?: string } | null>(null);

  // Stress Test Config
  const [users, setUsers] = useState(100);
  const [spawnRate, setSpawnRate] = useState(10);
  const [durationStr, setDurationStr] = useState("60s");

  // Execution State
  const [isRunning, setIsRunning] = useState(false);
  const [testId, setTestId] = useState<string | null>(null);
  const [showReport, setShowReport] = useState(false);
  const [chartData, setChartData] = useState<{ time: string; rps: number; p95: number }[]>([]);
  const [kpi, setKpi] = useState({
    totalRequests: 0,
    currentRps: 0,
    failures: 0,
    avgLatency: 0,
  });

  const pollInterval = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    // Load Test Cases on mount
    turboService.getApiTestCases().then(res => {
      setTestCases(res.items || []);
      if (res.items && res.items.length > 0) {
        setSelectedCase(res.items[0]);
      }
    });

    return () => {
      if (pollInterval.current) clearInterval(pollInterval.current);
    };
  }, []);

  const handleStart = async () => {
    if (!selectedCase) return;

    // 1. Reset state
    setChartData([]);
    setKpi({ totalRequests: 0, currentRps: 0, failures: 0, avgLatency: 0 });

    // 2. Call API to start
    setIsRunning(true);
    try {
      const res = await turboService.startStressTest({
        test_case_id: selectedCase.id,
        users,
        spawn_rate: spawnRate,
        duration: durationStr
      });
      const currentTestId = res.test_id || `mock-${Date.now()}`;
      setTestId(currentTestId);

      // 3. Start Polling
      pollInterval.current = setInterval(async () => {
        try {
          const stats = await turboService.getTestStats(currentTestId);

          setKpi({
            totalRequests: stats.total_requests,
            currentRps: stats.current_rps,
            failures: stats.total_failures,
            avgLatency: stats.avg_response_time
          });

          setChartData(prev => {
            const now = new Date().toLocaleTimeString();
            const newData = [...prev, {
              time: now,
              rps: stats.current_rps,
              p95: stats.p95_response_time
            }];
            // Keep last 60 data points for rolling effect
            if (newData.length > 60) return newData.slice(newData.length - 60);
            return newData;
          });

          if (stats.state === 'stopped' || stats.state === 'finished' || stats.state === 'failed') {
            if (pollInterval.current) clearInterval(pollInterval.current);
            setIsRunning(false);
            setShowReport(true);
          }
        } catch (e) {
          console.error("Polling error", e);
        }
      }, 1000);
    } catch (e) {
      console.error("Failed to start test", e);
      setIsRunning(false);
    }
  };

  const handleStop = async () => {
    if (pollInterval.current) {
      clearInterval(pollInterval.current);
      pollInterval.current = null;
    }
    setIsRunning(false);
    if (testId) {
      try {
        await turboService.stopStressTest(testId);
        setShowReport(true);
      } catch (e) {
        console.error("Failed to stop test", e);
      }
    }
  };

  return (
    <div className="flex h-[calc(100vh-4rem)] overflow-hidden text-slate-900">
      {/* LEFT PANEL: API Case List */}
      <div className="w-80 shrink-0 flex flex-col h-full rounded-3xl border border-white/70 bg-white/75 shadow-[12px_0_40px_-28px_rgba(14,165,233,0.5)] backdrop-blur-xl overflow-hidden">
        <div className="p-4 border-b border-sky-100 flex items-center justify-between">
          <h2 className="font-semibold flex items-center gap-2 text-slate-900">
            <Target className="w-5 h-5 text-emerald-500" />
            压测场景 (API Scenarios)
          </h2>
        </div>

        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {testCases.map((tc) => (
            <div
              key={tc.id}
              onClick={() => !isRunning && setSelectedCase(tc)}
              className={`p-3 rounded-2xl border cursor-pointer transition-all group ${selectedCase?.id === tc.id
                ? 'border-emerald-300 bg-gradient-to-r from-emerald-50 via-white to-sky-50 text-slate-950 shadow-sm ring-1 ring-emerald-200'
                : 'border-transparent bg-white/20 text-slate-700 hover:border-sky-200 hover:bg-white/80 hover:shadow-sm'
                } ${isRunning ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <div className="flex justify-between items-start">
                <div className="truncate font-medium text-sm">{tc.name}</div>
              </div>
              <div className="flex items-center gap-2 mt-2">
                <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono font-bold ${tc.method === 'GET' ? 'bg-blue-50 text-blue-700 border border-blue-200' :
                  tc.method === 'POST' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' :
                    'bg-orange-50 text-orange-700 border border-orange-200'
                  }`}>
                  {tc.method || 'GET'}
                </span>
                <span className="text-xs text-slate-500 font-mono truncate" title={tc.url}>{tc.url || '/'}</span>
              </div>
            </div>
          ))}
          {testCases.length === 0 && (
            <div className="p-4 text-center text-sm text-muted-foreground">
              未找到API测试用例 (No API Test Cases Found)
            </div>
          )}
        </div>
      </div>

      {/* RIGHT PANEL: Mission Control */}
      <div className="flex-1 flex flex-col h-full overflow-y-auto">
        <div className="p-6 max-w-6xl w-full mx-auto space-y-6">

          {/* TOP: Config & Ignition */}
          <Card className="shrink-0 rounded-2xl border-white/70 bg-white/80 shadow-[0_20px_60px_-35px_rgba(14,165,233,0.35)] backdrop-blur-xl">
            <CardHeader className="pb-4">
              <div className="flex justify-between items-start">
                <div>
                  <CardTitle className="text-2xl font-black bg-gradient-to-r from-emerald-600 via-sky-600 to-violet-600 bg-clip-text text-transparent flex items-center gap-2">
                    <Activity className="w-6 h-6 text-emerald-600" />
                    性能压测控制台 (Turbo Mission Control)
                  </CardTitle>
                  <CardDescription className="text-slate-600 mt-1">
                    目标 (Target): {selectedCase ? <span className="font-mono text-slate-800">{selectedCase.target_host || ''}{selectedCase.url || ''}</span> : '未选择 (None Selected)'}
                  </CardDescription>
                </div>

                <Button
                  onClick={isRunning ? handleStop : handleStart}
                  disabled={!selectedCase}
                  className={`h-14 px-8 text-lg font-bold uppercase tracking-wider transition-all duration-300 ${isRunning
                    ? 'bg-rose-500 hover:bg-rose-600 shadow-lg shadow-rose-500/25 text-white border-0'
                    : 'bg-gradient-to-r from-emerald-500 via-sky-500 to-violet-500 hover:from-emerald-600 hover:via-sky-600 hover:to-violet-600 shadow-lg shadow-sky-500/25 text-white border-0'
                    }`}
                >
                  {isRunning ? (
                    <><Square className="w-5 h-5 mr-2 fill-current" /> 紧急停止 (Emergency Stop)</>
                  ) : (
                    <><Play className="w-5 h-5 mr-2 fill-current" /> 启动压测 🚀 (Start Ignition 🚀)</>
                  )}
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-8">
                {/* Users Config */}
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <Label className="text-slate-700 flex items-center gap-2"><Users className="w-4 h-4 text-blue-400" /> 并发用户数 (Concurrent Users)</Label>
                    <span className="font-mono text-blue-400 font-bold">{users}</span>
                  </div>
                  <Slider
                    value={[users]}
                    min={1}
                    max={5000}
                    step={10}
                    onValueChange={(val) => setUsers(val[0])}
                    disabled={isRunning}
                    className="py-2"
                  />
                </div>

                {/* Spawn Rate Config */}
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <Label className="text-slate-700 flex items-center gap-2"><Zap className="w-4 h-4 text-yellow-400" /> 每秒生成数 (Spawn Rate / Sec)</Label>
                    <span className="font-mono text-yellow-400 font-bold">{spawnRate}</span>
                  </div>
                  <Slider
                    value={[spawnRate]}
                    min={1}
                    max={100}
                    step={1}
                    onValueChange={(val) => setSpawnRate(val[0])}
                    disabled={isRunning}
                    className="py-2"
                  />
                </div>

                {/* Duration Config */}
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <Label className="text-slate-700 flex items-center gap-2"><Clock className="w-4 h-4 text-purple-400" /> 压测时长 (Duration)</Label>
                    <span className="font-mono text-purple-400 font-bold">{durationStr}</span>
                  </div>
                  <Input
                    value={durationStr}
                    onChange={(e) => setDurationStr(e.target.value)}
                    disabled={isRunning}
                    className="bg-white/85 border-sky-200 text-slate-900 placeholder:text-slate-400 font-mono shadow-sm"
                    placeholder="e.g. 60s, 5m"
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* MIDDLE: KPI Cards */}
          <div className="grid grid-cols-4 gap-4 shrink-0">
            <Card className="rounded-2xl border-white/70 bg-white/80 shadow-[0_20px_60px_-35px_rgba(14,165,233,0.35)] backdrop-blur-xl">
              <CardContent className="p-4 flex flex-col gap-1">
                <span className="text-slate-400 text-sm font-medium">总请求数 (Total Requests)</span>
                <span className="text-3xl font-black font-mono text-slate-950">{kpi.totalRequests.toLocaleString()}</span>
              </CardContent>
            </Card>

            <Card className="rounded-2xl border-white/70 bg-white/80 shadow-[0_20px_60px_-35px_rgba(14,165,233,0.35)] backdrop-blur-xl">
              <CardContent className="p-4 flex flex-col gap-1">
                <span className="text-emerald-400/80 text-sm font-medium">当前吞吐量 (Current Throughput)</span>
                <span className="text-3xl font-black font-mono text-emerald-400">{kpi.currentRps.toFixed(1)} <span className="text-sm text-emerald-600">RPS</span></span>
              </CardContent>
            </Card>

            <Card className="rounded-2xl border-white/70 bg-white/80 shadow-[0_20px_60px_-35px_rgba(14,165,233,0.35)] backdrop-blur-xl">
              <CardContent className="p-4 flex flex-col gap-1">
                <span className="text-orange-400/80 text-sm font-medium">平均延迟 (Avg Latency)</span>
                <span className="text-3xl font-black font-mono text-orange-400">{kpi.avgLatency.toFixed(0)} <span className="text-sm text-orange-600">ms</span></span>
              </CardContent>
            </Card>

            <Card className="rounded-2xl border-white/70 bg-white/80 shadow-[0_20px_60px_-35px_rgba(14,165,233,0.35)] backdrop-blur-xl">
              <CardContent className="p-4 flex flex-col gap-1">
                <span className="text-rose-400/80 text-sm font-medium flex items-center gap-1">
                  失败数 (Failures) {kpi.failures > 0 && <AlertTriangle className="w-3 h-3 text-rose-500" />}
                </span>
                <span className={`text-3xl font-black font-mono ${kpi.failures > 0 ? 'text-rose-500' : 'text-slate-700'}`}>
                  {kpi.failures.toLocaleString()}
                </span>
              </CardContent>
            </Card>
          </div>

          {/* BOTTOM: Real-time Charts */}
          <div className="flex-1 flex gap-4 min-h-[300px]">
            <Card className="flex-1 flex flex-col overflow-hidden rounded-2xl border-white/70 bg-white/80 shadow-[0_20px_60px_-35px_rgba(14,165,233,0.35)] backdrop-blur-xl">
              <CardHeader className="py-3 px-4 shrink-0 border-b border-sky-100">
                <CardTitle className="text-sm font-medium text-emerald-400 flex items-center gap-2">
                  <Activity className="w-4 h-4" /> 吞吐量 (Throughput (RPS))
                </CardTitle>
              </CardHeader>
              <CardContent className="flex-1 p-0 px-2 pb-2 min-h-0">
                <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
                  <AreaChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="colorRps" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#39ff14" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#39ff14" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                    <XAxis dataKey="time" hide />
                    <YAxis stroke="#94a3b8" tick={{ fill: '#64748b', fontSize: 12 }} />
                    <RechartsTooltip
                      contentStyle={{ backgroundColor: 'rgba(255,255,255,0.92)', border: '1px solid #bae6fd', borderRadius: '12px', color: '#0f172a' }}
                      itemStyle={{ color: '#059669', fontWeight: 'bold' }}
                      labelStyle={{ color: '#64748b' }}
                    />
                    <Area type="monotone" dataKey="rps" stroke="#39ff14" strokeWidth={2} fillOpacity={1} fill="url(#colorRps)" isAnimationActive={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card className="flex-1 flex flex-col overflow-hidden rounded-2xl border-white/70 bg-white/80 shadow-[0_20px_60px_-35px_rgba(14,165,233,0.35)] backdrop-blur-xl">
              <CardHeader className="py-3 px-4 shrink-0 border-b border-sky-100">
                <CardTitle className="text-sm font-medium text-orange-500 flex items-center gap-2">
                  <Clock className="w-4 h-4" /> P95延迟 (P95 Latency (ms))
                </CardTitle>
              </CardHeader>
              <CardContent className="flex-1 p-0 px-2 pb-2 min-h-0">
                <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
                  <LineChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                    <XAxis dataKey="time" hide />
                    <YAxis stroke="#94a3b8" tick={{ fill: '#64748b', fontSize: 12 }} />
                    <RechartsTooltip
                      contentStyle={{ backgroundColor: 'rgba(255,255,255,0.92)', border: '1px solid #fed7aa', borderRadius: '12px', color: '#0f172a' }}
                      itemStyle={{ color: '#ea580c', fontWeight: 'bold' }}
                      labelStyle={{ color: '#64748b' }}
                    />
                    <Line type="monotone" dataKey="p95" stroke="#ff4500" strokeWidth={2} dot={false} isAnimationActive={false} />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </div>

        </div>
      </div>

      {/* FINAL REPORT DIALOG */}
      <Dialog open={showReport} onOpenChange={setShowReport}>
        <DialogContent className="border-slate-200 bg-white text-slate-900 shadow-2xl sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle className="text-xl font-bold flex items-center gap-2 text-emerald-700">
              <Target className="w-5 h-5" /> 压测报告摘要 (Final Report Summary)
            </DialogTitle>
            <DialogDescription className="text-slate-600">
              压测已结束，以下是本次性能测试的最终指标。 (The stress test has ended. Here are the final metrics.)
            </DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-4 py-4">
            <div className="bg-sky-50/70 p-4 rounded-2xl flex flex-col gap-1 border border-sky-100">
              <span className="text-sm text-slate-500">总请求数 (Total Requests)</span>
              <span className="text-2xl font-mono font-bold text-slate-950">{kpi.totalRequests.toLocaleString()}</span>
            </div>
            <div className="bg-sky-50/70 p-4 rounded-2xl flex flex-col gap-1 border border-sky-100">
              <span className="text-sm text-slate-500">最终吞吐量 (Final RPS)</span>
              <span className="text-2xl font-mono font-bold text-emerald-400">{kpi.currentRps.toFixed(1)}</span>
            </div>
            <div className="bg-sky-50/70 p-4 rounded-2xl flex flex-col gap-1 border border-sky-100">
              <span className="text-sm text-slate-500">平均延迟 (Avg Latency)</span>
              <span className="text-2xl font-mono font-bold text-orange-400">{kpi.avgLatency.toFixed(0)} ms</span>
            </div>
            <div className="bg-sky-50/70 p-4 rounded-2xl flex flex-col gap-1 border border-sky-100">
              <span className="text-sm text-slate-500">失败数 (Failures)</span>
              <span className={`text-2xl font-mono font-bold ${kpi.failures > 0 ? 'text-rose-500' : 'text-emerald-500'}`}>{kpi.failures.toLocaleString()}</span>
            </div>
          </div>
          <DialogFooter>
            <Button onClick={() => setShowReport(false)} className="bg-gradient-to-r from-sky-500 via-blue-500 to-violet-500 text-white shadow-lg shadow-sky-500/25 hover:from-sky-600 hover:via-blue-600 hover:to-violet-600">
              关闭 (Close)
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
