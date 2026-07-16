'use client';

import { useEffect, useState } from 'react';

interface Step {
  id: number;
  label: string;
  duration: number; // Duration in ms to wait before moving to next step
}

const STEPS: Step[] = [
  { id: 1, label: '安全分诊评估...', duration: 600 },
  { id: 2, label: '症状特征提取与整合...', duration: 1200 },
  { id: 3, label: '检索医学指南与知识库...', duration: 1200 },
  { id: 4, label: '整合生成个性化诊疗建议...', duration: 99999 }, // Keep waiting on last step
];

export default function ProgressIndicator() {
  const [currentStep, setCurrentStep] = useState(1);

  useEffect(() => {
    let timer: NodeJS.Timeout;
    
    const runNext = (stepIndex: number) => {
      if (stepIndex >= STEPS.length) return;
      const step = STEPS[stepIndex];
      timer = setTimeout(() => {
        setCurrentStep(step.id + 1);
        runNext(stepIndex + 1);
      }, step.duration);
    };

    runNext(0);

    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="flex flex-col gap-2 p-4 bg-gray-50 dark:bg-gray-800/50 rounded-xl border border-gray-100 dark:border-gray-700/50 max-w-sm mb-4 animate-fade-in shadow-sm">
      <div className="flex items-center gap-2 mb-1">
        <div className="w-2 h-2 bg-blue-500 rounded-full animate-ping" />
        <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">AI 诊断进行中</span>
      </div>
      
      <div className="flex flex-col gap-3">
        {STEPS.map((step) => {
          const isPending = step.id > currentStep;
          const isActive = step.id === currentStep;
          const isCompleted = step.id < currentStep;

          return (
            <div key={step.id} className="flex items-center gap-2.5 transition-all duration-300">
              {/* 状态圈圈 */}
              <div className="flex items-center justify-center">
                {isCompleted && (
                  <div className="w-4 h-4 rounded-full bg-green-500 flex items-center justify-center text-[10px] text-white font-bold">
                    ✓
                  </div>
                )}
                {isActive && (
                  <div className="w-4 h-4 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" />
                )}
                {isPending && (
                  <div className="w-4 h-4 rounded-full border border-gray-300 dark:border-gray-600" />
                )}
              </div>

              {/* 步骤文字 */}
              <span className={`text-xs ${
                isCompleted ? 'text-green-600 dark:text-green-500 line-through opacity-70' :
                isActive ? 'text-gray-800 dark:text-gray-100 font-medium' :
                'text-gray-400 dark:text-gray-500'
              }`}>
                {step.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
