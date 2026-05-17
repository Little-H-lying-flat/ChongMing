import { Rocket } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

interface ComingSoonProps {
    title: string;
}

export function ComingSoon({ title }: ComingSoonProps) {
    return (
        <div className="flex h-full items-center justify-center">
            <Card className="w-full max-w-md rounded-3xl border-white/70 bg-white/80 text-slate-900 shadow-[0_24px_70px_-32px_rgba(14,165,233,0.45)] backdrop-blur-xl">
                <CardContent className="flex flex-col items-center justify-center space-y-6 p-12 text-center">
                    <div className="relative">
                        <div className="absolute -inset-2 animate-pulse rounded-full bg-sky-400/20 blur-xl"></div>
                        <div className="relative rounded-full border border-sky-100 bg-gradient-to-br from-sky-50 to-violet-50 p-4 shadow-lg shadow-sky-500/20">
                            <Rocket className="h-12 w-12 text-sky-600" />
                        </div>
                    </div>

                    <div className="space-y-2">
                        <h1 className="bg-gradient-to-r from-sky-600 via-blue-600 to-violet-600 bg-clip-text text-2xl font-bold tracking-tight text-transparent">
                            {title}
                        </h1>
                        <p className="text-sm text-slate-600">
                            该核心业务模块正在研发与接入中... (This module is under development...)
                        </p>
                    </div>

                    <div className="h-1 w-full overflow-hidden rounded-full bg-sky-100">
                        <div className="h-full w-1/3 animate-[shimmer_2s_infinite] bg-gradient-to-r from-sky-400 via-blue-500 to-violet-500"></div>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
