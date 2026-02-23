"use client";

import React, { useEffect, useState } from "react";
import {
  PlayCircle, CheckCircle2, Server, BrainCircuit,
  TrendingUp, TrendingDown, Database
} from "lucide-react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { getDashboardOverview, DashboardResponse } from "@/services/dashboardService";
import { toast } from "sonner";

const COLORS = ['#3b82f6', '#8b5cf6', '#10b981', '#f43f5e'];

export default function OverviewPage() {
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const res = await getDashboardOverview();
        setData(res);
      } catch (error) {
        // console.error("Failed to load dashboard data:", error); // Next.js Turbopack crashes on this
        toast.error("加载大盘数据失败，请检查后端服务是否已完全启动 (Failed to load dashboard. Check if backend is running)");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading || !data) {
    return (
      <div className="space-y-6">
        <div>
          <Skeleton className="h-10 w-64 bg-slate-800" />
          <Skeleton className="h-4 w-96 mt-2 bg-slate-800" />
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-32 w-full bg-slate-900 rounded-xl" />)}
        </div>
        <div className="grid gap-4 md:grid-cols-7">
          <Skeleton className="col-span-4 h-[400px] bg-slate-900 rounded-xl" />
          <Skeleton className="col-span-3 h-[400px] bg-slate-900 rounded-xl" />
        </div>
      </div>
    );
  }

  const { kpis, trend, defects, recent_activities } = data;

  const kpiCards = [
    {
      title: "总执行记录 (Total Executions)",
      value: kpis.total_executions,
      trend: "平台累计调度 (Platform cumulative)",
      isUp: true,
      icon: PlayCircle,
      color: "text-blue-400"
    },
    {
      title: "全局通过率 (Global Pass Rate)",
      value: kpis.global_pass_rate,
      trend: "基于历史所有执行 (Based on all history)",
      isUp: parseFloat(kpis.global_pass_rate) >= 90,
      icon: CheckCircle2,
      color: "text-emerald-400"
    },
    {
      title: "活跃测试环境 (Active Environments)",
      value: kpis.active_environments,
      trend: kpis.db_status === "正常" ? "数据库已连接 (DB Connected)" : "数据库异常 (DB Error)",
      isUp: kpis.db_status === "正常",
      icon: Server,
      color: "text-purple-400"
    },
    {
      title: "引擎神经元状态 (Engine Neuron Status)",
      value: kpis.omniparser_status,
      trend: "双瞳视觉解析 (Dual Pupil Vision)",
      isUp: kpis.omniparser_status === "正常",
      icon: BrainCircuit,
      color: "text-cyan-400"
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-3xl font-bold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-cyan-300">
          核心大盘概览 (Core Dashboard Overview)
        </h2>
        <p className="text-slate-400 mt-1 flex items-center gap-2">
          基于双瞳架构的全局测试质量报告 (Global quality report powered by Neural-Phoenix)
          {kpis.db_status === "异常" && (
            <Badge variant="destructive" className="ml-2 bg-rose-500/10 text-rose-400 hover:bg-rose-500/20">
              <Database className="w-3 h-3 mr-1" /> DB Disconnected
            </Badge>
          )}
        </p>
      </div>

      {/* KPI Cards (Tier 1) */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {kpiCards.map((item, index) => (
          <Card key={index} className="bg-slate-900 border-slate-800 shadow-xl relative overflow-hidden group">
            <div className="absolute inset-0 bg-gradient-to-br from-white/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
            <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
              <CardTitle className="text-sm font-medium text-slate-300">
                {item.title}
              </CardTitle>
              <item.icon className={`h-5 w-5 ${item.color}`} />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-white mb-1">{item.value}</div>
              <p className={`text-xs flex items-center ${item.isUp ? 'text-emerald-400' : 'text-rose-400'}`}>
                {item.isUp ? <TrendingUp className="w-3 h-3 mr-1" /> : <TrendingDown className="w-3 h-3 mr-1" />}
                {item.trend}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Charts (Tier 2) */}
      <div className="grid gap-4 md:grid-cols-7">
        <Card className="col-span-4 bg-slate-900 border-slate-800 shadow-xl">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              执行趋势分析 (Execution Trend Analysis (Last 7 Days))
            </CardTitle>
            <CardDescription className="text-slate-400">成功与失败的自动化执行数量趋势 (Success vs failure automation execution trends)</CardDescription>
          </CardHeader>
          <CardContent className="pt-4 pb-2">
            {trend.length > 0 ? (
              <div style={{ width: '100%', height: 300, position: 'relative' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={trend} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="colorPassed" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="colorFailed" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#f43f5e" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                    <XAxis dataKey="date" stroke="#64748b" tick={{ fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                    <YAxis stroke="#64748b" tick={{ fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                    <RechartsTooltip
                      contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '8px' }}
                      itemStyle={{ color: '#e2e8f0' }}
                    />
                    <Area type="monotone" dataKey="passed" name="成功 (Passed)" stroke="#3b82f6" strokeWidth={2} fillOpacity={1} fill="url(#colorPassed)" />
                    <Area type="monotone" dataKey="failed" name="失败 (Failed)" stroke="#f43f5e" strokeWidth={2} fillOpacity={1} fill="url(#colorFailed)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="flex items-center justify-center h-[300px] text-slate-500 text-sm">暂无趋势数据 (No trend data)</div>
            )}
          </CardContent>
        </Card>

        <Card className="col-span-3 bg-slate-900 border-slate-800 shadow-xl">
          <CardHeader>
            <CardTitle>AI缺陷归因透视 (AI Defect Attribution)</CardTitle>
            <CardDescription className="text-slate-400">基于近期的失败测试数据聚类 (Clustering based on recent failure data)</CardDescription>
          </CardHeader>
          <CardContent className="pt-4 pb-2">
            {defects.length > 0 ? (
              <div style={{ width: '100%', height: 300, position: 'relative' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={defects}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={80}
                      paddingAngle={5}
                      dataKey="value"
                      stroke="none"
                    >
                      {defects.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <RechartsTooltip
                      contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '8px' }}
                      itemStyle={{ color: '#e2e8f0' }}
                    />
                    <Legend verticalAlign="bottom" height={36} wrapperStyle={{ color: '#94a3b8' }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="flex items-center justify-center h-full text-slate-500 text-sm">暂无缺陷数据 (No defect data (100% pass))</div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Activity Feed (Tier 3) */}
      <Card className="bg-slate-900 border-slate-800 shadow-xl">
        <CardHeader>
          <CardTitle>最新执行轨迹 (Latest Execution Traces)</CardTitle>
          <CardDescription className="text-slate-400">平台最新的自动化调度与巡检记录 (Latest automation dispatch and inspection records)</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {recent_activities.length === 0 && (
              <div className="text-center text-slate-500 py-8">暂无近期执行记录 (No recent executions)</div>
            )}
            {recent_activities.map((activity) => (
              <div key={activity.id} className="flex items-center justify-between p-4 rounded-lg bg-slate-800/50 border border-slate-700/50 hover:bg-slate-800 transition-colors">
                <div className="flex items-center gap-4">
                  <div className="mt-1">
                    {activity.status === 'passed' && <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]" />}
                    {activity.status === 'failed' && <div className="w-2.5 h-2.5 rounded-full bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.5)]" />}
                    {activity.status === 'error' && <div className="w-2.5 h-2.5 rounded-full bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.5)]" />}
                    {activity.status === 'running' && <div className="w-2.5 h-2.5 rounded-full bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.8)] animate-pulse" />}
                    {activity.status === 'pending' && <div className="w-2.5 h-2.5 rounded-full bg-slate-500" />}
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold text-slate-200">{activity.scenario}</h4>
                    <div className="flex items-center gap-3 mt-1 text-xs text-slate-400">
                      <span>{activity.id}</span>
                      <span>•</span>
                      <span>{activity.time}</span>
                      <span>•</span>
                      <span>耗时 (Duration): {activity.duration}</span>
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  {activity.error || activity.status === 'failed' || activity.status === 'error' ? (
                    <Badge variant="destructive" className="bg-rose-500/10 text-rose-400 border border-rose-500/20 hover:bg-rose-500/20">
                      {activity.error || "执行失败 (Execution Failed)"}
                    </Badge>
                  ) : activity.status === 'running' || activity.status === 'pending' ? (
                    <Badge variant="secondary" className="bg-blue-500/10 text-blue-400 border border-blue-500/20 hover:bg-blue-500/20">
                      处理中... (Processing...)
                    </Badge>
                  ) : (
                    <Badge variant="outline" className="border-emerald-500/30 text-emerald-400">
                      通过 (Passed)
                    </Badge>
                  )}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
