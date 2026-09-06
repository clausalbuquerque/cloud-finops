import { useState, useRef, useEffect, Component } from 'react';
import type { ReactNode, KeyboardEvent, FormEvent } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Send, Bot, User, Loader2, BrainCircuit, ChevronDown, ChevronRight, X, Maximize2, Minimize2 } from 'lucide-react';

class ErrorBoundary extends Component<{children: ReactNode}, {hasError: boolean, error: Error | null}> {
  constructor(props: any) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }
  render() {
    if (this.state.hasError) {
      return <div className="text-red-500 text-xs p-2">MD Err: {this.state.error?.message}</div>;
    }
    return this.props.children;
  }
}

interface Message {
  role: 'user' | 'model';
  content: string;
  thoughts?: string;
  suggestions?: string[];
}

interface ChatPanelProps {
  isOpen: boolean;
  onClose: () => void;
  contextText?: string;
}

export default function ChatPanel({ isOpen, onClose, contextText }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'model', content: "Hi! Ask me any questions about your Cloud FinOps data." }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [expandedThoughts, setExpandedThoughts] = useState<Record<number, boolean>>({});
  const [isExpanded, setIsExpanded] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading, isExpanded]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      const scrollHeight = textareaRef.current.scrollHeight;
      textareaRef.current.style.height = Math.min(scrollHeight, 112) + 'px';
      textareaRef.current.style.overflowY = scrollHeight > 112 ? 'auto' : 'hidden';
    }
  }, [input]);

  const toggleThought = (idx: number) => {
    setExpandedThoughts(prev => ({ ...prev, [idx]: !prev[idx] }));
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend(e);
    }
  };

  const handleSend = async (e?: FormEvent | KeyboardEvent, overrideText: string | null = null) => {
    e?.preventDefault();
    const textToSend = overrideText || input;
    if (!textToSend.trim() || isLoading) return;

    if (!overrideText) setInput('');
    setIsLoading(true);

    const currentMessages: Message[] = [...messages, { role: 'user', content: textToSend.trim() }];
    
    const nextIdx = currentMessages.length;
    let thinking = '';
    let reply = '';
    const suggestions: string[] = [];

    setMessages([...currentMessages, { role: 'model', content: '', thoughts: '', suggestions: [] }]);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: contextText ? `[Context: ${contextText}] ${textToSend.trim()}` : textToSend.trim(),
          history: currentMessages.slice(0, -1)
        })
      });

      if (!response.body) throw new Error("No response body");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.replace('data: ', '').trim();
            if (dataStr === '[DONE]') break;
            if (dataStr) {
              try {
                const parsed = JSON.parse(dataStr);
                if (parsed.type === 'THOUGHT') {
                  thinking += parsed.content + '\n';
                } else if (parsed.type === 'SUGGESTION') {
                  suggestions.push(parsed.content);
                } else {
                  reply += parsed.content;
                }

                setMessages(prev => {
                  const updated = [...prev];
                  updated[nextIdx] = {
                    role: 'model',
                    content: reply,
                    thoughts: thinking,
                    suggestions: suggestions
                  };
                  return updated;
                });
              } catch (e) {
                console.error('JSON parse fail:', dataStr);
              }
            }
          }
        }
      }
    } catch (error) {
      console.error(error);
      setMessages([...currentMessages, { role: 'model', content: `⚠️ Error connecting to server.` }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className={`fixed top-0 right-0 h-full ${isExpanded ? 'w-[800px]' : 'w-[400px]'} bg-white dark:bg-[#1a1a1a] shadow-2xl flex flex-col transition-all duration-300 z-50 ${isOpen ? 'translate-x-0' : 'translate-x-full'}`}>
      <div className="flex items-center justify-between p-4 border-b border-zinc-200 dark:border-zinc-800">
        <div className="font-semibold text-zinc-900 dark:text-white">Ask AI</div>
        <div className="flex items-center gap-2">
          <button onClick={() => setIsExpanded(!isExpanded)} className="text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200 transition-colors p-1">
            {isExpanded ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
          <button onClick={onClose} className="text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200 transition-colors p-1">
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
        {messages.map((m, i) => (
          <div key={i} className={`flex gap-3 ${m.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
            <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${m.role === 'user' ? 'bg-blue-600 text-white' : 'bg-zinc-200 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300'}`}>
              {m.role === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
            </div>
            <div className="max-w-[85%] flex flex-col gap-2">
              
              {m.role === 'model' && m.thoughts && m.thoughts.trim().length > 0 && (
                <div className="bg-zinc-50 dark:bg-[#1e1e1e] border border-zinc-200 dark:border-zinc-700/60 rounded-xl overflow-hidden shadow-sm">
                  <button
                    onClick={() => toggleThought(i)}
                    className="w-full flex items-center gap-2 px-3 py-2 text-xs font-medium text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-800/50"
                  >
                    {expandedThoughts[i] ? <ChevronDown className="w-3.5 h-3.5 flex-shrink-0" /> : <ChevronRight className="w-3.5 h-3.5 flex-shrink-0" />}
                    <BrainCircuit className="w-3.5 h-3.5 text-blue-400 flex-shrink-0" />
                    <span className="truncate text-left">
                      {(() => {
                        if (m.content && m.content.length > 0) return "View reasoning process";
                        const lines = m.thoughts.split('\n').filter(l => l.trim().length > 0);
                        return lines.length > 0 ? lines[lines.length - 1] : "Analyzing context...";
                      })()}
                    </span>
                  </button>
                  {expandedThoughts[i] && (
                    <div className="px-3 pb-3 pt-3 border-t border-zinc-200 dark:border-zinc-800/50 max-h-[350px] overflow-y-auto bg-zinc-100/50 dark:bg-black/20 text-xs font-mono leading-relaxed flex flex-col gap-3">
                      {m.thoughts.split('\n').filter(l => l.trim().length > 0).map((line, idx) => (
                        <div key={idx} className="bg-white dark:bg-[#262626] border border-zinc-200 dark:border-zinc-700/50 rounded-lg p-3 shadow-sm flex items-start gap-3">
                          <div className="text-blue-500 mt-0.5 flex-shrink-0">
                            <BrainCircuit className="w-4 h-4" />
                          </div>
                          <div className="break-words whitespace-pre-wrap text-zinc-700 dark:text-zinc-300">
                            {line}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {m.role === 'model' && !m.content && (
                <div className="flex items-center gap-2 text-xs text-zinc-500 italic ml-1 mb-1 p-1">
                  <Loader2 className="w-3 h-3 animate-spin" /> {m.thoughts ? 'Thinking...' : 'Gathering insights...'}
                </div>
              )}

              {m.content && (
                <div className={`p-3 rounded-2xl text-sm leading-relaxed ${m.role === 'user' ? 'bg-blue-600 text-white rounded-tr-none' : 'bg-zinc-100 dark:bg-[#262626] text-zinc-800 dark:text-zinc-200 rounded-tl-none border border-zinc-200 dark:border-zinc-700/50 shadow-sm'}`}>
                  {m.role === 'model' ? (
                    <ErrorBoundary>
                      <div className="prose prose-sm dark:prose-invert max-w-none [&>p]:mb-2 [&>p:last-child]:mb-0 [&>ul]:list-disc [&>ul]:ml-5 [&>h3]:font-semibold [&>h3]:text-zinc-800 dark:[&>h3]:text-zinc-100 [&>h3]:mb-1 [&>h3]:mt-3 [&>ol]:list-decimal [&>ol]:ml-5 [&_code]:bg-black/5 dark:[&_code]:bg-black/30 [&_code]:px-1.5 [&_code]:rounded [&_pre]:bg-black/5 dark:[&_pre]:bg-black/30 [&_pre]:p-3 [&_pre]:rounded-lg [&_pre]:overflow-x-auto [&_table]:w-full [&_table]:mb-3 [&_th]:border-b [&_th]:border-zinc-300 dark:[&_th]:border-zinc-700 [&_th]:pb-1 [&_td]:border-b [&_td]:border-zinc-200 dark:[&_td]:border-zinc-800 [&_td]:py-1">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {m.content}
                        </ReactMarkdown>
                      </div>
                    </ErrorBoundary>
                  ) : (
                    <div className="whitespace-pre-wrap">{m.content}</div>
                  )}
                </div>
              )}

              {m.role === 'model' && m.suggestions && m.suggestions.length > 0 && (
                <div className="flex flex-col gap-1.5 mt-2">
                  {m.suggestions.slice(0, 3).map((s, idx) => (
                    <button
                      key={idx} onClick={() => handleSend(undefined, s)} disabled={isLoading}
                      className="text-left text-xs bg-blue-50 dark:bg-blue-900/20 hover:bg-blue-100 dark:hover:bg-blue-800/40 text-blue-700 dark:text-blue-300 p-2 rounded-lg border border-blue-200 dark:border-blue-800/30 transition-colors"
                    >{s}</button>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={handleSend} className="p-4 border-t border-zinc-200 dark:border-zinc-800 flex items-end bg-zinc-50 dark:bg-[#0c0c0f] relative">
        <textarea
          ref={textareaRef}
          value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={handleKeyDown} disabled={isLoading}
          placeholder="Ask a question..."
          rows={1}
          className="w-full bg-white dark:bg-[#1a1a1a] border border-zinc-300 dark:border-zinc-700 rounded-xl pl-4 pr-12 py-3 text-sm focus:outline-none focus:border-blue-500 text-zinc-800 dark:text-zinc-100 placeholder-zinc-500 dark:placeholder-zinc-400 resize-none overscroll-contain"
        />
        <button type="submit" disabled={!input.trim() || isLoading} className="absolute right-6 bottom-6 p-2 bg-blue-600 hover:bg-blue-700 rounded-full text-white transition-colors disabled:opacity-50">
          <Send className="w-4 h-4" />
        </button>
      </form>
    </div>
  );
}
