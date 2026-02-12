import React from 'react';
import RightPupilDebugger from './components/debug/RightPupilDebugger';

function App() {
    return (
        <div className="min-h-screen bg-gray-100 p-4 font-sans">
            <header className="mb-8 border-b pb-4">
                <div className="max-w-4xl mx-auto flex justify-between items-center">
                    <h1 className="text-2xl font-bold text-gray-800">ChongMing (重明)</h1>
                    <span className="text-sm text-gray-500">Right Pupil Engine Debugger</span>
                </div>
            </header>
            <main>
                <RightPupilDebugger />
            </main>
        </div>
    );
}

export default App;
