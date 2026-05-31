import React, { useState, useEffect } from 'react';
import { Search, Loader2, Sparkles, TrendingUp, Package, AlertTriangle, ToggleLeft, ToggleRight } from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function App() {
  const [sku, setSku] = useState('');
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [toast, setToast] = useState(null);

  // Состояние сплеш-скрина загрузки
  const [appInit, setAppInit] = useState(true);

  // ИИ
  const [aiLoading, setAiLoading] = useState(false);
  const [aiReport, setAiReport] = useState(null);
  const [aiError, setAiError] = useState(null);

  useEffect(() => {
    // Имитация загрузки приложения с нашим маскотом-рыбаком
    const timer = setTimeout(() => setAppInit(false), 2000);
    return () => clearTimeout(timer);
  }, []);

  const showToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(null), 4000);
  };

  const handleMonitorClick = () => {
    showToast("Режим 24/7 доступен в Pro-версии. Бот будет проверять конкурентов раз в сутки");
  };

  const fetchAnalysis = async () => {
    if (!sku) return;
    setLoading(true);
    setError(null);
    setData(null);
    setAiReport(null);
    setAiError(null);

    try {
      const res = await fetch(`${API_BASE_URL}/api/analyze/${sku}`, {
        headers: { 
          'X-API-Key': 'super_secret_wb_key_123',
          'Bypass-Tunnel-Reminder': 'true'
        }
      });
      const result = await res.json();
      if (!res.ok) {
        throw new Error(result.detail || 'Ошибка при получении данных');
      }
      setData(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchAiReport = async () => {
    if (!data) return;
    setAiLoading(true);
    setAiError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/ai-report`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': 'super_secret_wb_key_123',
          'Bypass-Tunnel-Reminder': 'true'
        },
        body: JSON.stringify(data)
      });
      const result = await res.json();
      if (!res.ok) {
        throw new Error(result.detail || 'Гуру медитирует и не отвечает.');
      }
      setAiReport(result);
    } catch (err) {
      setAiError(err.message);
    } finally {
      setAiLoading(false);
    }
  };

  // Splash Screen
  if (appInit) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-[#0b1120]">
        <div className="relative">
          <img src="/loading.png" alt="Loading mascot" className="w-48 h-48 object-contain animate-pulse drop-shadow-[0_0_20px_rgba(72,229,194,0.4)]" />
        </div>
        <h1 className="mt-8 text-2xl font-bold tracking-widest text-[#48E5C2] neon-text-glow">ИНИЦИАЛИЗАЦИЯ...</h1>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-4 sm:p-6 lg:p-8 max-w-4xl mx-auto flex flex-col gap-8 relative z-0">
      {/* Background Image with Transparency */}
      <div 
        className="fixed inset-0 -z-10 bg-[url('/loading.png')] bg-cover bg-center bg-no-repeat opacity-15 mix-blend-luminosity"
      ></div>
      {/* Dark gradient overlay to ensure text readability */}
      <div className="fixed inset-0 -z-10 bg-slate-900/60"></div>
      {/* Toast Notification */}
      {toast && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 glass-panel border border-[#48E5C2]/40 rounded-xl px-4 py-3 shadow-lg shadow-[#48E5C2]/10 flex items-center gap-3 animate-in fade-in slide-in-from-top-4">
          <AlertTriangle className="w-5 h-5 text-[#48E5C2]" />
          <p className="text-sm font-medium text-slate-200">{toast}</p>
        </div>
      )}

      {/* Header */}
      <header className="flex items-center justify-between glass-panel rounded-2xl px-6 py-4">
        <div className="flex items-center gap-4">
          <img src="/logo.png" alt="Logo" className="h-16 w-16 sm:h-20 sm:w-20 object-contain drop-shadow-[0_0_12px_rgba(72,229,194,0.6)] hover:scale-105 transition-transform" />
          <h1 className="text-xl sm:text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-400">
            WB SpyGlass
          </h1>
        </div>
        <button onClick={handleMonitorClick} className="flex items-center gap-2 group transition-opacity hover:opacity-80">
          <span className="text-sm font-medium text-slate-400 group-hover:text-slate-300 hidden sm:inline">24/7 Мониторинг</span>
          <ToggleLeft className="w-8 h-8 text-slate-500" />
        </button>
      </header>

      {/* Step 1: Search */}
      <section className="glass-panel rounded-2xl p-6 sm:p-8">
        <h2 className="text-sm font-bold tracking-wider text-slate-400 uppercase mb-6 flex items-center gap-2">
          <Search className="w-4 h-4" /> Шаг 1. Сбор данных
        </h2>
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
            <input 
              type="text" 
              placeholder="Введите артикул (SKU)" 
              className="w-full bg-slate-900/50 border border-slate-700 rounded-xl py-3 pl-12 pr-4 text-white placeholder-slate-500 focus:outline-none focus:border-[#48E5C2] focus:ring-1 focus:ring-[#48E5C2] transition-all"
              value={sku}
              onChange={e => setSku(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && fetchAnalysis()}
              disabled={loading}
            />
          </div>
          <button 
            onClick={fetchAnalysis}
            disabled={loading || !sku}
            className="flex items-center justify-center gap-2 bg-[#48E5C2] hover:bg-[#2F9E85] text-slate-900 font-bold py-3 px-8 rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-[0_0_15px_rgba(72,229,194,0.4)] hover:shadow-[0_0_25px_rgba(72,229,194,0.6)]"
          >
            {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : "Анализировать"}
          </button>
        </div>
        {error && (
          <div className="mt-4 flex items-start gap-2 text-rose-400 bg-rose-950/30 p-4 rounded-xl border border-rose-900/50">
            <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
            <p className="text-sm">{error}</p>
          </div>
        )}
      </section>

      {/* Results */}
      {data && (
        <div className="flex flex-col gap-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
          
          {/* Target Product */}
          <div className="glass-panel rounded-2xl p-6 border-l-4 border-l-[#48E5C2]">
            <h3 className="text-xs font-bold tracking-wider text-[#48E5C2] uppercase mb-3">Наш товар</h3>
            <div className="flex justify-between items-start gap-4">
              <div>
                <h4 className="text-lg font-medium text-white mb-1">{data.target_product.name}</h4>
                <p className="text-sm text-slate-400 mb-3">{data.target_product.brand}</p>
                <div className="flex items-center gap-4 text-sm">
                  <span className="flex items-center gap-1 text-amber-400 bg-amber-400/10 px-2 py-1 rounded-md">
                    ★ {data.target_product.rating}
                  </span>
                  <span className="text-slate-400">{data.target_product.feedbacks} отз.</span>
                </div>
              </div>
              <div className="text-right">
                <div className="text-2xl font-bold text-white mb-1">{data.target_product.price}</div>
                <div className="text-xs text-slate-500">Арт: {data.target_product.sku}</div>
              </div>
            </div>
          </div>

          {/* Competitors */}
          <div className="glass-panel rounded-2xl p-6">
            <h3 className="text-xs font-bold tracking-wider text-slate-400 uppercase mb-4">Топ-5 конкурентов</h3>
            <div className="flex flex-col gap-3">
              {data.competitors.length === 0 ? (
                <p className="text-sm text-slate-400 italic">Конкуренты не найдены (возможно, товар уникален или нет данных в категории).</p>
              ) : (
                data.competitors.map((comp, idx) => (
                  <a 
                    href={comp.url} 
                    target="_blank" 
                    rel="noopener noreferrer" 
                    key={idx} 
                    className="flex items-center justify-between p-3 rounded-xl bg-slate-800/40 border border-slate-700/50 hover:border-[#48E5C2]/50 hover:bg-slate-800/80 transition-all cursor-pointer group"
                  >
                    <div className="flex items-center gap-3 overflow-hidden">
                      <div className="w-6 h-6 rounded-full bg-slate-700 group-hover:bg-[#48E5C2]/20 text-slate-300 group-hover:text-[#48E5C2] flex items-center justify-center text-xs font-bold shrink-0 transition-colors">
                        {idx + 1}
                      </div>
                      <div className="truncate">
                        <div className="text-sm font-medium text-slate-200 group-hover:text-white truncate transition-colors">{comp.name}</div>
                        <div className="text-xs text-slate-500 group-hover:text-slate-400 transition-colors">{comp.brand} · {comp.feedbacks} отз.</div>
                      </div>
                    </div>
                    <div className="text-sm font-bold text-white shrink-0 ml-4 group-hover:text-[#48E5C2] transition-colors">{comp.price}</div>
                  </a>
                ))
              )}
            </div>
            <p className="mt-6 text-[11px] text-center text-slate-500 leading-relaxed">
              Самые сильные конкуренты выбраны по алгоритму: 1) Точное семантическое совпадение с целевым предметом. 2) Максимальное количество отзывов. 3) Рейтинг ≥ 4.5.
            </p>
          </div>

          {/* Step 2: AI Button (только если есть конкуренты) */}
          {!aiReport && data.competitors.length > 0 && (
            <button 
              onClick={fetchAiReport}
              disabled={aiLoading}
              className="mt-2 w-full glass-panel border-[#48E5C2]/30 hover:border-[#48E5C2]/60 hover:bg-[#48E5C2]/5 rounded-2xl p-6 flex flex-col items-center justify-center gap-3 transition-all group disabled:opacity-70 disabled:cursor-wait"
            >
              {aiLoading ? (
                <div className="flex flex-col items-center gap-4 w-full">
                  <Loader2 className="w-8 h-8 text-[#48E5C2] animate-spin" />
                  <div className="w-3/4 max-w-md h-2 bg-slate-800 rounded-full overflow-hidden">
                    <div className="h-full bg-[#48E5C2] w-1/3 animate-pulse rounded-full shadow-[0_0_10px_#48E5C2]"></div>
                  </div>
                  <p className="text-sm text-[#48E5C2] neon-text-glow font-medium animate-pulse">Гуру анализирует карточки конкурентов...</p>
                </div>
              ) : (
                <>
                  <Sparkles className="w-8 h-8 text-[#48E5C2] group-hover:scale-110 transition-transform drop-shadow-[0_0_8px_rgba(72,229,194,0.8)]" />
                  <span className="text-lg font-bold text-slate-200 group-hover:text-white">🪄 Умный SEO-разбор от Гуру</span>
                </>
              )}
            </button>
          )}

          {/* AI Error */}
          {aiError && (
            <div className="glass-panel border-amber-500/30 bg-amber-950/20 rounded-2xl p-6 flex items-start gap-4">
              <AlertTriangle className="w-6 h-6 text-amber-400 shrink-0" />
              <div>
                <h3 className="text-amber-400 font-bold mb-1">Гуру на Бали 🌴</h3>
                <p className="text-sm text-slate-300">{aiError}</p>
              </div>
            </div>
          )}

          {/* AI Report Render */}
          {aiReport && (
            <div className="glass-panel rounded-2xl p-6 sm:p-8 border border-[#48E5C2]/30 animate-in zoom-in-95 duration-500 relative overflow-hidden">
              {/* Декоративный неон */}
              <div className="absolute -top-20 -right-20 w-64 h-64 bg-[#48E5C2] rounded-full mix-blend-screen filter blur-[100px] opacity-10 pointer-events-none"></div>
              
              <h2 className="text-lg font-bold text-white mb-8 flex items-center gap-3">
                <Sparkles className="w-5 h-5 text-[#48E5C2]" /> 
                Результаты SEO-анализа
              </h2>

              <div className="space-y-8">
                {/* Идеальный заголовок */}
                <div>
                  <h3 className="text-xs font-bold tracking-wider text-slate-400 uppercase mb-3">Идеальный заголовок</h3>
                  <div className="bg-[#48E5C2]/10 border border-[#48E5C2]/30 rounded-xl p-4 text-slate-100 font-medium leading-relaxed">
                    {aiReport.optimized_title}
                  </div>
                </div>

                {/* Упущенные ключи */}
                <div>
                  <h3 className="text-xs font-bold tracking-wider text-slate-400 uppercase mb-3 flex items-center gap-2">
                    <TrendingUp className="w-4 h-4 text-[#48E5C2]" />
                    Упущенные ключи
                  </h3>
                  {aiReport.missing_keywords && aiReport.missing_keywords.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {aiReport.missing_keywords.map((kw, i) => (
                        <span key={i} className="px-3 py-1.5 rounded-lg bg-[#48E5C2]/10 text-[#48E5C2] border border-[#48E5C2]/20 text-xs font-medium tracking-wide">
                          {kw}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-slate-400 italic">Все важные ключи уже используются.</p>
                  )}
                </div>

                {/* Рекомендации */}
                <div>
                  <h3 className="text-xs font-bold tracking-wider text-slate-400 uppercase mb-3">Рекомендации Гуру</h3>
                  <div className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">
                    {aiReport.recommendations}
                  </div>
                </div>
              </div>
            </div>
          )}

        </div>
      )}
    </div>
  );
}
