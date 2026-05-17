"use client";

import { useEffect, useState } from "react";
import { Activity, AlertCircle, Loader2 } from "lucide-react";

interface HealthData {
    status: string;
    services: {
        api: string;
        database: string;
        redis: string;
        celery: string;
        omniparser?: string;
    };
}

import { api } from "@/services/api";

export function VisionStatus() {
    const [health, setHealth] = useState<HealthData | null>(null);
    const [loading, setLoading] = useState(true);

    const fetchHealth = async () => {
        try {
            const { data } = await api.get<HealthData>("/health");
            setHealth(data);
        } catch (_error) {
            // Silently handle fetch failures for background polling 
            // to avoid triggering the Next.js Error Overlay when the backend restarts.
            setHealth(null);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchHealth();
        const interval = setInterval(fetchHealth, 10000); // Check every 10s
        return () => clearInterval(interval);
    }, []);

    const getStatusInfo = () => {
        const opStatus = health?.services.omniparser;

        if (loading && !health) {
            return {
                label: "加载中... (Loading...)",
                color: "bg-slate-500",
                icon: <Loader2 className="w-3 h-3 animate-spin" />,
                description: "检测视觉执行器状态中... (Detecting vision executor status...)"
            };
        }

        switch (opStatus) {
            case "ok":
                return {
                    label: "视觉执行器就绪 (Vision Ready)",
                    color: "bg-emerald-500",
                    icon: <Activity className="w-3 h-3 text-white" />,
                    description: "视觉解析服务在线且已就绪。 (Visual Parsing Service is online and ready.)"
                };
            case "loading":
                return {
                    label: "模型加载中 (Model Loading)",
                    color: "bg-amber-500",
                    icon: <Loader2 className="w-3 h-3 animate-spin text-white" />,
                    description: "视觉执行器正在启动，请稍候。 (Vision executor is starting. Please wait.)"
                };
            case "down":
            default:
                return {
                    label: "视觉执行器离线 (Vision Offline)",
                    color: "bg-rose-500",
                    icon: <AlertCircle className="w-3 h-3 text-white" />,
                    description: "视觉执行器状态不可用，当前运行会继续使用已配置的执行策略。 (Vision executor status is unavailable; runs continue with the configured strategy.)"
                };
        }
    };

    const status = getStatusInfo();

    return (
        <div
            className="flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-slate-800/50 cursor-help transition-colors group"
            title={status.description}
        >
            <div className={`w-2 h-2 rounded-full ${status.color} shadow-[0_0_8px_rgba(0,0,0,0.5)] group-hover:shadow-[0_0_12px_${status.color === 'bg-emerald-500' ? '#10b981' : (status.color === 'bg-amber-500' ? '#f59e0b' : '#f43f5e')}]`} />
            <div className="flex flex-col">
                <span className="text-[10px] uppercase tracking-wider font-bold text-slate-500 group-hover:text-slate-400">
                    Vision
                </span>
                <span className="text-xs font-medium text-slate-300 group-hover:text-white transition-colors">
                    {status.label}
                </span>
            </div>
        </div>
    );
}
