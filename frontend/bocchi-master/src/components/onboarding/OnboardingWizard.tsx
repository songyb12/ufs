import { useState, useCallback } from 'react'
import type { InstrumentConfig } from '../../types/music'
import { INSTRUMENTS, STANDARD_GUITAR, STANDARD_BASS } from '../../constants/tunings'

interface OnboardingWizardProps {
  onComplete: (instrument: InstrumentConfig, goToCurriculum: boolean) => void
}

type Step = 'welcome' | 'instrument' | 'tuning' | 'first-chord' | 'next-step'

const STEPS: Step[] = ['welcome', 'instrument', 'tuning', 'first-chord', 'next-step']

export function OnboardingWizard({ onComplete }: OnboardingWizardProps) {
  const [step, setStep] = useState<Step>('welcome')
  const [instrumentType, setInstrumentType] = useState<'guitar' | 'bass'>('guitar')
  const [selectedInstrument, setSelectedInstrument] = useState<InstrumentConfig>(STANDARD_GUITAR)

  const stepIndex = STEPS.indexOf(step)
  const progress = ((stepIndex + 1) / STEPS.length) * 100

  const next = useCallback(() => {
    const idx = STEPS.indexOf(step)
    if (idx < STEPS.length - 1) setStep(STEPS[idx + 1])
  }, [step])

  const prev = useCallback(() => {
    const idx = STEPS.indexOf(step)
    if (idx > 0) setStep(STEPS[idx - 1])
  }, [step])

  const handleInstrumentType = useCallback((type: 'guitar' | 'bass') => {
    setInstrumentType(type)
    setSelectedInstrument(type === 'guitar' ? STANDARD_GUITAR : STANDARD_BASS)
  }, [])

  const handleTuningSelect = useCallback((inst: InstrumentConfig) => {
    setSelectedInstrument(inst)
  }, [])

  const handleFinish = useCallback((goToCurriculum: boolean) => {
    onComplete(selectedInstrument, goToCurriculum)
  }, [onComplete, selectedInstrument])

  const filteredInstruments = INSTRUMENTS.filter(i => i.type === instrumentType)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div
        className="bg-slate-800 border border-slate-700 rounded-xl shadow-2xl max-w-lg w-full mx-4 animate-fade-in overflow-hidden"
      >
        {/* Progress bar */}
        <div className="h-1 bg-slate-700">
          <div
            className="h-full bg-orange-500 transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>

        <div className="p-6">
          {/* Step: Welcome */}
          {step === 'welcome' && (
            <div className="text-center space-y-4">
              <div className="text-5xl">🎸</div>
              <h1 className="text-2xl font-bold text-white">Bocchi-master</h1>
              <p className="text-slate-400 text-sm leading-relaxed">
                기타/베이스 연습을 도와주는 앱입니다.<br />
                간단한 설정을 마치면 바로 시작할 수 있어요.
              </p>
              <button
                onClick={next}
                className="px-6 py-2.5 bg-orange-600 hover:bg-orange-500 text-white font-medium rounded-lg transition-colors"
              >
                시작하기
              </button>
            </div>
          )}

          {/* Step: Instrument Type */}
          {step === 'instrument' && (
            <div className="space-y-4">
              <h2 className="text-lg font-bold text-white">어떤 악기를 연주하나요?</h2>
              <div className="grid grid-cols-2 gap-3">
                <button
                  onClick={() => handleInstrumentType('guitar')}
                  className={`p-4 rounded-lg border-2 transition-colors text-center ${
                    instrumentType === 'guitar'
                      ? 'border-orange-500 bg-orange-500/10'
                      : 'border-slate-600 bg-slate-700/50 hover:border-slate-500'
                  }`}
                >
                  <div className="text-3xl mb-2">🎸</div>
                  <div className={`font-medium ${instrumentType === 'guitar' ? 'text-orange-400' : 'text-slate-300'}`}>
                    Guitar
                  </div>
                  <div className="text-xs text-slate-500 mt-1">6-string, 7-string</div>
                </button>
                <button
                  onClick={() => handleInstrumentType('bass')}
                  className={`p-4 rounded-lg border-2 transition-colors text-center ${
                    instrumentType === 'bass'
                      ? 'border-orange-500 bg-orange-500/10'
                      : 'border-slate-600 bg-slate-700/50 hover:border-slate-500'
                  }`}
                >
                  <div className="text-3xl mb-2">🎵</div>
                  <div className={`font-medium ${instrumentType === 'bass' ? 'text-orange-400' : 'text-slate-300'}`}>
                    Bass
                  </div>
                  <div className="text-xs text-slate-500 mt-1">4, 5, 6-string</div>
                </button>
              </div>
              <div className="flex justify-between pt-2">
                <button onClick={prev} className="px-4 py-2 text-sm text-slate-400 hover:text-slate-200 transition-colors">
                  뒤로
                </button>
                <button onClick={next} className="px-5 py-2 bg-orange-600 hover:bg-orange-500 text-white text-sm font-medium rounded-lg transition-colors">
                  다음
                </button>
              </div>
            </div>
          )}

          {/* Step: Tuning */}
          {step === 'tuning' && (
            <div className="space-y-4">
              <h2 className="text-lg font-bold text-white">튜닝을 선택하세요</h2>
              <p className="text-xs text-slate-500">잘 모르겠다면 Standard를 선택하세요. 나중에 언제든 바꿀 수 있어요.</p>
              <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                {filteredInstruments.map((inst) => (
                  <button
                    key={inst.name}
                    onClick={() => handleTuningSelect(inst)}
                    className={`w-full text-left px-3 py-2 rounded-lg transition-colors flex items-center justify-between ${
                      selectedInstrument.name === inst.name
                        ? 'bg-orange-500/15 border border-orange-500/40 text-orange-300'
                        : 'bg-slate-700/50 border border-transparent text-slate-300 hover:bg-slate-700'
                    }`}
                  >
                    <span className="text-sm font-medium">{inst.name}</span>
                    <span className="text-xs text-slate-500 font-mono">
                      {inst.tuning.map(n => n.name).join(' ')}
                    </span>
                  </button>
                ))}
              </div>
              <div className="flex justify-between pt-2">
                <button onClick={prev} className="px-4 py-2 text-sm text-slate-400 hover:text-slate-200 transition-colors">
                  뒤로
                </button>
                <button onClick={next} className="px-5 py-2 bg-orange-600 hover:bg-orange-500 text-white text-sm font-medium rounded-lg transition-colors">
                  다음
                </button>
              </div>
            </div>
          )}

          {/* Step: First Chord */}
          {step === 'first-chord' && (
            <div className="space-y-4">
              <h2 className="text-lg font-bold text-white">
                {instrumentType === 'guitar' ? '첫 코드: Em' : '첫 음: Open String'}
              </h2>
              {instrumentType === 'guitar' ? (
                <div className="space-y-3">
                  <p className="text-sm text-slate-400">
                    Em(이마이너)는 가장 쉬운 코드입니다. 두 손가락만 사용하세요.
                  </p>
                  {/* Simple Em chord diagram */}
                  <div className="bg-slate-900 rounded-lg p-4 font-mono text-sm">
                    <div className="text-center space-y-0.5">
                      <div className="text-xs text-slate-500 mb-2">Em chord</div>
                      <div className="text-slate-400">e |---<span className="text-emerald-400">0</span>---</div>
                      <div className="text-slate-400">B |---<span className="text-emerald-400">0</span>---</div>
                      <div className="text-slate-400">G |---<span className="text-emerald-400">0</span>---</div>
                      <div className="text-slate-400">D |---<span className="text-orange-400">2</span>---  (middle finger)</div>
                      <div className="text-slate-400">A |---<span className="text-orange-400">2</span>---  (index finger)</div>
                      <div className="text-slate-400">E |---<span className="text-emerald-400">0</span>---</div>
                    </div>
                  </div>
                  <p className="text-xs text-slate-500">
                    프렛보드에서 이 코드를 찾아보세요. 앱의 코드 진행 기능에서 다양한 코드를 연습할 수 있습니다.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  <p className="text-sm text-slate-400">
                    먼저 각 개방현의 소리를 익혀보세요.
                  </p>
                  <div className="bg-slate-900 rounded-lg p-4 font-mono text-sm">
                    <div className="text-center space-y-0.5">
                      <div className="text-xs text-slate-500 mb-2">Open strings (Standard)</div>
                      <div className="text-slate-400">G |---<span className="text-emerald-400">0</span>---  (가장 얇은 줄)</div>
                      <div className="text-slate-400">D |---<span className="text-emerald-400">0</span>---</div>
                      <div className="text-slate-400">A |---<span className="text-emerald-400">0</span>---</div>
                      <div className="text-slate-400">E |---<span className="text-emerald-400">0</span>---  (가장 두꺼운 줄)</div>
                    </div>
                  </div>
                  <p className="text-xs text-slate-500">
                    프렛보드를 클릭하면 소리를 들을 수 있습니다. 메트로놈에 맞춰 한 줄씩 연습해보세요.
                  </p>
                </div>
              )}
              <div className="flex justify-between pt-2">
                <button onClick={prev} className="px-4 py-2 text-sm text-slate-400 hover:text-slate-200 transition-colors">
                  뒤로
                </button>
                <button onClick={next} className="px-5 py-2 bg-orange-600 hover:bg-orange-500 text-white text-sm font-medium rounded-lg transition-colors">
                  다음
                </button>
              </div>
            </div>
          )}

          {/* Step: Next Step */}
          {step === 'next-step' && (
            <div className="space-y-4">
              <h2 className="text-lg font-bold text-white">준비 완료!</h2>
              <p className="text-sm text-slate-400">
                어디서 시작할지 선택하세요.
              </p>
              <div className="space-y-2.5">
                <button
                  onClick={() => handleFinish(true)}
                  className="w-full p-3.5 rounded-lg border-2 border-orange-500/40 bg-orange-500/10 hover:bg-orange-500/20 transition-colors text-left"
                >
                  <div className="font-medium text-orange-300">📚 커리큘럼 모드 (추천)</div>
                  <div className="text-xs text-slate-400 mt-1">
                    단계별 레슨과 드릴로 체계적으로 배우기
                  </div>
                </button>
                <button
                  onClick={() => handleFinish(false)}
                  className="w-full p-3.5 rounded-lg border-2 border-slate-600 bg-slate-700/50 hover:border-slate-500 transition-colors text-left"
                >
                  <div className="font-medium text-slate-300">🎸 자유 연습 모드</div>
                  <div className="text-xs text-slate-500 mt-1">
                    프렛보드, 메트로놈, 코드 진행 등 자유롭게 탐색
                  </div>
                </button>
              </div>
              <div className="pt-2">
                <button onClick={prev} className="px-4 py-2 text-sm text-slate-400 hover:text-slate-200 transition-colors">
                  뒤로
                </button>
              </div>
            </div>
          )}

          {/* Step indicator */}
          <div className="flex justify-center gap-1.5 mt-5">
            {STEPS.map((s, i) => (
              <div
                key={s}
                className={`w-2 h-2 rounded-full transition-colors ${
                  i <= stepIndex ? 'bg-orange-500' : 'bg-slate-600'
                }`}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
