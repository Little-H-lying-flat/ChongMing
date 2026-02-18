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

export function OmniParserStatus() {
    const [health, setHealth] = useState<HealthData | null>(null);
    const [loading, setLoading] = useState(true);

    const fetchHealth = async () => {
        try {
            const res = await fetch("/api/v1/health");
            if (res.ok) {
                const data = await res.json();
                setHealth(data);
            }
        } catch (error) {
            console.error("Failed to fetch health:", error);
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
                label: "Loading...",
                color: "bg-slate-500",
                icon: <Loader2 className="w-3 h-3 animate-spin" />,
                description: "Detecting OmniParser status..."
            };
        }

        switch (opStatus) {
            case "ok":
                return {
                    label: "OmniParser Ready",
                    color: "bg-emerald-500",
                    icon: <Activity className="w-3 h-3 text-white" />,
                    description: "Visual Parsing Service is online and ready."
                };
            case "loading":
                return {
                    label: "Model Loading",
                    color: "bg-amber-500",
                    icon: <Loader2 className="w-3 h-3 animate-spin text-white" />,
                    description: "OmniParser is starting up and loading weights. Please wait."
                };
            case "down":
            default:
                return {
                    label: "OmniParser Offline",
                    color: "bg-rose-500",
                    icon: <AlertCircle className="w-3 h-3 text-white" />,
                    description: "OmniParser service is unreachable. AI Agent will fallback to DOM strategy."
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
                    OmniParser
                </span>
                <span className="text-xs font-medium text-slate-300 group-hover:text-white transition-colors">
                    {status.label}
                </span>
            </div>
        </div>
    );
}
