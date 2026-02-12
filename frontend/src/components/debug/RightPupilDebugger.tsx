import React, { useState } from 'react';
import { runUiTask, ExecutionResult, TraceLog } from '../../services/api';

const RightPupilDebugger: React.FC = () => {
    const [url, setUrl] = useState('https://www.google.com');
    const [prompt, setPrompt] = useState('Type "OpenAI" in the search box and click search');
    const [logs, setLogs] = useState<ExecutionResult | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleRun = async () => {
        setLoading(true);
        setError(null);
        setLogs(null);
        try {
            const result = await runUiTask(prompt, url);
            setLogs(result);
        } catch (err: any) {
            setError(err.message || 'Unknown error occurred');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="p-6 bg-gray-50 min-h-screen">
            <div className="max-w-4xl mx-auto bg-white rounded-xl shadow-md overflow-hidden p-6">
                <h1 className="text-2xl font-bold mb-4 text-gray-800 flex items-center gap-2">
                    👁️ Right Pupil Debugger
                </h1>

                {/* Input Area */}
                <div className="space-y-4 mb-6">
                    <div>
                        <label className="block text-sm font-medium text-gray-700">Target URL</label>
                        <input
                            type="text"
                            value={url}
                            onChange={(e) => setUrl(e.target.value)}
                            className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-700">Task Prompt</label>
                        <textarea
                            value={prompt}
                            onChange={(e) => setPrompt(e.target.value)}
                            rows={3}
                            className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                        />
                    </div>

                    <button
                        onClick={handleRun}
                        disabled={loading}
                        className={`w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white 
              ${loading ? 'bg-blue-300 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700 focus:ring-2 focus:ring-offset-2 focus:ring-blue-500'}
            `}
                    >
                        {loading ? 'Running Automation (Please Wait)...' : 'Run Task'}
                    </button>
                </div>

                {/* Status & Error */}
                {error && (
                    <div className="mb-4 p-4 bg-red-50 border-l-4 border-red-500 text-red-700">
                        <p className="font-bold">Error</p>
                        <p>{error}</p>
                    </div>
                )}

                {/* Timeline Results */}
                {logs && (
                    <div className="border-t pt-4">
                        <h2 className="text-lg font-semibold mb-3">Execution Timeline</h2>
                        <div className="space-y-4">
                            {logs.map((step: TraceLog, index) => (
                                <div key={index} className={`p-4 rounded-lg border ${step.status === 'success' ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
                                    <div className="flex justify-between items-start">
                                        <div>
                                            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800 mb-2">
                                                Step {step.step || index + 1}
                                            </span>
                                            <h3 className="text-md font-bold text-gray-900">
                                                {step.action?.action_type?.toUpperCase()}
                                            </h3>
                                            <p className="text-sm text-gray-600 mt-1">
                                                Target: <code className="bg-gray-100 px-1 rounded">{step.action?.target?.value}</code>
                                                ({step.action?.target?.strategy})
                                            </p>
                                            {step.stable_selector && (
                                                <p className="text-xs text-gray-500 mt-1">
                                                    Select: <code className="bg-gray-100 px-1 rounded">{step.stable_selector}</code>
                                                </p>
                                            )}
                                            {step.details && (
                                                <p className="text-sm text-gray-700 mt-2 italic">{step.details}</p>
                                            )}
                                        </div>

                                        <div className="text-right">
                                            <span className={`px-2 py-1 text-xs rounded-full font-semibold ${step.status === 'success' ? 'text-green-800 bg-green-100' : 'text-red-800 bg-red-100'
                                                }`}>
                                                {step.status}
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default RightPupilDebugger;
