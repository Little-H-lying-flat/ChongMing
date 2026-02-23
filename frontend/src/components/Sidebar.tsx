"use client";

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { LayoutDashboard, Activity, Play, Server, Database, Zap, Brain, ShieldAlert, Settings } from 'lucide-react'
import { Button } from './ui/button'

const Sidebar = () => {
  const pathname = usePathname()

  const navItems = [
    { name: '总览大盘 (Overview)', path: '/', icon: LayoutDashboard },
    { name: '需求解析 (Design)', path: '/design', icon: Activity },
    { name: '调度大盘 (Executions)', path: '/executions', icon: Play },
    { name: '视觉UI (Visual UI)', path: '/visual-ui', icon: Server },
    { name: '接口自动化 (API Auto)', path: '/api-auto', icon: Database },
    { name: '性能压测 (Performance)', path: '/performance', icon: Zap },
    { name: '智能运维 (Smart Ops)', path: '/smart-ops', icon: ShieldAlert },
    { name: '模型治理 (Model Config)', path: '/model-config', icon: Brain },
    { name: '系统设置 (Settings)', path: '/settings', icon: Settings },
  ]

  return (
    <div className="flex flex-col h-screen w-64 bg-slate-900 text-white border-r border-slate-800">
      <div className="p-6 border-b border-slate-800">
        <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-cyan-300 bg-clip-text text-transparent">ChongMing</h1>
        <p className="text-xs text-slate-400 mt-1">智能测试平台 (Intelligent Test Platform)</p>
      </div>

      <nav className="flex-1 p-4 space-y-2">
        {navItems.map((item) => {
          const Icon = item.icon
          const isActive = pathname === item.path
          return (
            <Link key={item.path} href={item.path}>
              <Button
                variant={isActive ? 'secondary' : 'ghost'}
                className={`w-full justify-start gap-3 ${isActive
                  ? 'bg-slate-800 text-blue-400'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800'
                  }`}
              >
                <Icon className="w-5 h-5" />
                {item.name}
              </Button>
            </Link>
          )
        })}
      </nav>

      <div className="p-4 border-t border-slate-800 space-y-4">
        {/* Mock OmniParser Status */}
        <div
          className="flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-slate-800/50 cursor-help transition-colors group"
          title="检测OmniParser状态... (Detecting OmniParser Status)"
        >
          <div className={`w-2 h-2 rounded-full shadow-[0_0_8px_rgba(0,0,0,0.5)] bg-slate-500`} />
          <div className="flex flex-col">
            <span className="text-[10px] uppercase tracking-wider font-bold text-slate-500 group-hover:text-slate-400">OmniParser</span>
            <span className="text-xs font-medium text-slate-300 group-hover:text-white transition-colors">
              加载中... (Loading...)
            </span>
          </div>
        </div>

        {/* User Info */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center font-bold">
            CM
          </div>
          <div>
            <p className="text-sm font-medium">管理员 (Admin User)</p>
            <p className="text-xs text-slate-500">admin@chongming.ai</p>
          </div>
        </div>
      </div>
    </div>
  )
}

export { Sidebar }
