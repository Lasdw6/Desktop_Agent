import { useState, useEffect, useCallback } from "react";
import "./App.css";

interface Message {
  text: string;
  sender: "user" | "bot";
  hasImage?: boolean;
  imageData?: string;
  prompt?: string;
}

interface AutomationState {
  isActive: boolean;
  goal: string;
  stepCount: number;
  completed: boolean;
  lastInstruction: string;
  isAutomatic: boolean;
  autoDelay: number; // seconds
}

interface AutomationResponse {
  instruction: string;
  completed: boolean;
  next_action: string;
  coordinates?: [number, number];
  text_to_type?: string;
  screenshot?: string;
  prompt?: string;
}

interface ActionLog {
  id: number;
  timestamp: string;
  action_type: string;
  description: string;
  coordinates?: [number, number];
  text_content?: string;
  success: boolean;
  error_message?: string;
}

// --- Simple orchestration helpers (Electron + Python backend) ---
async function getScreenshot(): Promise<string | null> {
  try {
    const res = await fetch("http://localhost:5000/screenshot");
    const data = await res.json();
    return data.screenshot || null;
  } catch {
    return null;
  }
}

async function getUiSummary(): Promise<any | null> {
  try {
    // Hide overlay so our own UI is not included in Windows UIA discovery
    await (window as any).overlayAPI?.hideOverlay?.();
    await new Promise((r) => setTimeout(r, 120));

    const res = await fetch("http://localhost:5000/ui-summary?method=windows");
    const data = await res.json();
    return data;
  } catch {
    return null;
  } finally {
    try { await (window as any).overlayAPI?.showOverlay?.(); } catch {}
  }
}

async function chatWithVision(message: string, imageData: string): Promise<string> {
  const res = await fetch("http://localhost:5000/chat-vision", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, image_data: imageData })
  });
  const data = await res.json();
  return data.response || "";
}

async function executeAction(instruction: string): Promise<string> {
  const res = await fetch("http://localhost:5000/execute-action", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ instruction })
  });
  const data = await res.json();
  return data.result || data.error || "";
}

async function orchestrateStart(goal: string): Promise<AutomationResponse> {
  const screenshot = await getScreenshot();
  const summary = await getUiSummary();
  const prompt = `AUTOMATION TASK: ${goal}\n\nHOST SCREEN SUMMARY:\n${JSON.stringify(summary, null, 2)}\n\nPlease output a single next action as a concise instruction. Prefer element-aware actions (e.g., Click \"[ElementName]\"). Fallback to coordinates as \"Click (x, y)\". If typing, use \"Type \"text\"\".`;
  const visionText = screenshot ? await chatWithVision(prompt, screenshot) : "";
  const finalInstruction = (visionText && visionText.trim()) || goal;
  await executeAction(finalInstruction);
  return {
    instruction: finalInstruction,
    completed: false,
    next_action: finalInstruction,
    screenshot: screenshot || undefined,
    prompt
  };
}

async function orchestrateContinue(goal: string, previousInstruction: string, stepCount: number): Promise<AutomationResponse> {
  const screenshot = await getScreenshot();
  const summary = await getUiSummary();
  const prompt = `CONTINUE AUTOMATION (step ${stepCount + 1}) for: ${goal}\nPrevious instruction: ${previousInstruction}\n\nHOST SCREEN SUMMARY:\n${JSON.stringify(summary, null, 2)}\n\nOutput the next single action.`;
  const visionText = screenshot ? await chatWithVision(prompt, screenshot) : "";
  const finalInstruction = (visionText && visionText.trim()) || previousInstruction || `Click (10, 10)`;
  await executeAction(finalInstruction);
  return {
    instruction: finalInstruction,
    completed: false,
    next_action: finalInstruction,
    screenshot: screenshot || undefined,
    prompt
  };
}

function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [capturedImage, setCapturedImage] = useState<string | null>(null);
  const [actionLogs, setActionLogs] = useState<ActionLog[]>([]);
  const [showActionLogs, setShowActionLogs] = useState(false);
  const [panelOpen, setPanelOpen] = useState<boolean>(true);
  const [panelOpaque, setPanelOpaque] = useState<boolean>(false);
  // Removed unused expandedPrompts state
  type NotchDock = 'left' | 'center' | 'right';
  const [notchDock, setNotchDock] = useState<NotchDock>('center');
  const [isDraggingNotch, setIsDraggingNotch] = useState<boolean>(false);
  const [dragX, setDragX] = useState<number>(0);

  const [automationState, setAutomationState] = useState<AutomationState>({
    isActive: false,
    goal: "",
    stepCount: 0,
    completed: false,
    lastInstruction: "",
    isAutomatic: false,
    autoDelay: 3, // 3 seconds default
  });
  const [countdown, setCountdown] = useState<number>(0);

  // Simple auto-resize function
  const autoResize = async () => {};

  // Trigger resize when content changes
  useEffect(() => {
    const timer = setTimeout(autoResize, 100);
    return () => clearTimeout(timer);
  }, [messages.length, capturedImage, isLoading]);

  // Define continueAutomation with useCallback to avoid dependency issues
  const continueAutomation = useCallback(async () => {
    if (!automationState.isActive) return;

    setIsLoading(true);
    
    // Add a message indicating we're continuing
    const continueMessage: Message = {
      text: "📷 Taking new screenshot and analyzing...",
      sender: "user",
    };
    setMessages(prev => [...prev, continueMessage]);

    try {
      const response = await orchestrateContinue(automationState.goal, automationState.lastInstruction, automationState.stepCount);

      const botMessage: Message = {
        text: `Step ${automationState.stepCount + 1}: ${response.instruction}`,
        sender: "bot",
        hasImage: !!response.screenshot,
        imageData: response.screenshot,
        prompt: response.prompt,
      };
      setMessages(prev => [...prev, botMessage]);

      setAutomationState(prev => ({
        ...prev,
        stepCount: prev.stepCount + 1,
        completed: response.completed,
        isActive: !response.completed,
        lastInstruction: response.instruction,
      }));
    } catch (error) {
      console.error("Automation continue error:", error);
      const errorMessage: Message = {
        text: "Sorry, there was an error continuing the automation.",
        sender: "bot",
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  }, [automationState.isActive, automationState.goal, automationState.lastInstruction, automationState.stepCount]);

  // Automatic mode timer
  useEffect(() => {
    if (automationState.isActive && automationState.isAutomatic && !isLoading && !automationState.completed) {
      setCountdown(automationState.autoDelay);
      
      const countdownInterval = setInterval(() => {
        setCountdown(prev => {
          if (prev <= 1) {
            clearInterval(countdownInterval);
            continueAutomation();
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
      
      return () => {
        clearInterval(countdownInterval);
        setCountdown(0);
      };
    } else {
      setCountdown(0);
    }
  }, [automationState.isActive, automationState.isAutomatic, automationState.stepCount, isLoading, automationState.completed, continueAutomation]);

  // Manual resize for testing
  const manualResize = () => {};

  // Notch drag handlers
  const onNotchDragStart = (e: React.MouseEvent) => {
    (window as any).overlayAPI?.setInteractive(true);
    setIsDraggingNotch(true);
    setDragX(e.clientX);
    // prevent text selection while dragging
    e.preventDefault();
  };

  const onGlobalMouseMove = useCallback((e: MouseEvent) => {
    if (!isDraggingNotch) return;
    setDragX(e.clientX);
  }, [isDraggingNotch]);

  const onGlobalMouseUp = useCallback(() => {
    if (!isDraggingNotch) return;
    const w = window.innerWidth;
    const x = dragX;
    const edgeThreshold = Math.max(120, Math.floor(w * 0.1));
    if (x <= edgeThreshold) setNotchDock('left');
    else if (x >= w - edgeThreshold) setNotchDock('right');
    else setNotchDock('center');
    setIsDraggingNotch(false);
    (window as any).overlayAPI?.setInteractive(false);
  }, [isDraggingNotch, dragX]);

  useEffect(() => {
    window.addEventListener('mousemove', onGlobalMouseMove);
    window.addEventListener('mouseup', onGlobalMouseUp);
    return () => {
      window.removeEventListener('mousemove', onGlobalMouseMove);
      window.removeEventListener('mouseup', onGlobalMouseUp);
    };
  }, [onGlobalMouseMove, onGlobalMouseUp]);

  const getPreviewDock = (): 'left' | 'center' | 'right' => {
    const w = window.innerWidth;
    const x = dragX;
    const edgeThreshold = Math.max(120, Math.floor(w * 0.1));
    if (x <= edgeThreshold) return 'left';
    if (x >= w - edgeThreshold) return 'right';
    return 'center';
  };



  const captureScreen = async () => {
    try {
      // Hide overlay to avoid capturing it in the screenshot
      await (window as any).overlayAPI?.hideOverlay?.();
      // Slight delay to ensure the window is hidden by the OS compositor
      await new Promise((r) => setTimeout(r, 120));

      const res = await fetch("http://localhost:5000/screenshot");
      const json = await res.json();

      // Show overlay back
      await (window as any).overlayAPI?.showOverlay?.();

      if (json.screenshot) setCapturedImage(json.screenshot);
    } catch (error) {
      console.error("Capture error:", error);
      try { await (window as any).overlayAPI?.showOverlay?.(); } catch {}
    }
  };

  const sendMessage = async () => {
    if (!input.trim() && !capturedImage) return;

    const userMessage: Message = {
      text: input,
      sender: "user",
      hasImage: !!capturedImage,
      imageData: capturedImage || undefined,
    };

    setMessages(prev => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      let response: string;
      if (capturedImage) {
        const res = await fetch("http://localhost:5000/chat-vision", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: input || "What do you see in this image?", image_data: capturedImage })
        });
        const data = await res.json();
        response = (data.response && String(data.response).trim()) || data.error || "(no response)";
        setCapturedImage(null);
      } else {
        const res = await fetch("http://localhost:5000/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: input })
        });
        const data = await res.json();
        response = (data.response && String(data.response).trim()) || data.error || "(no response)";
      }

      const botMessage: Message = {
        text: response,
        sender: "bot",
      };

      setMessages(prev => [...prev, botMessage]);
    } catch (error) {
      console.error("Send error:", error);
      const errorMessage: Message = {
        text: "Sorry, there was an error processing your request.",
        sender: "bot",
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };



  const clearImage = () => {
    setCapturedImage(null);
  };

  const startAutomation = async () => {
    if (!input.trim()) return;

    const goal = input.trim();
    setInput("");
    setIsLoading(true);
    
    // Add the goal as a user message
    const userMessage: Message = {
      text: `🤖 AUTOMATION: ${goal}`,
      sender: "user",
    };
    setMessages(prev => [...prev, userMessage]);

    try {
      const response = await orchestrateStart(goal);
      
      const botMessage: Message = {
        text: `Step 1: ${response.instruction}`,
        sender: "bot",
        hasImage: !!response.screenshot,
        imageData: response.screenshot,
        prompt: response.prompt,
      };
      setMessages(prev => [...prev, botMessage]);

      setAutomationState(prev => ({
        ...prev,
        isActive: !response.completed,
        goal,
        stepCount: 1,
        completed: response.completed,
        lastInstruction: response.instruction,
      }));
    } catch (error) {
      console.error("Automation start error:", error);
      const errorMessage: Message = {
        text: "Sorry, there was an error starting the automation.",
        sender: "bot",
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };



  const stopAutomation = () => {
    setCountdown(0);
    
    setAutomationState({
      isActive: false,
      goal: "",
      stepCount: 0,
      completed: false,
      lastInstruction: "",
      isAutomatic: false,
      autoDelay: 3,
    });
    
    const stopMessage: Message = {
      text: "🛑 Automation stopped by user.",
      sender: "bot",
    };
    setMessages(prev => [...prev, stopMessage]);
  };

  const toggleAutomaticMode = () => {
    setAutomationState(prev => ({
      ...prev,
      isAutomatic: !prev.isAutomatic,
    }));
    
    setCountdown(0);
  };

  const adjustAutoDelay = (newDelay: number) => {
    setAutomationState(prev => ({
      ...prev,
      autoDelay: Math.max(1, Math.min(10, newDelay)), // Clamp between 1-10 seconds
    }));
  };

  // Action Log Functions
  const fetchActionLogs = async () => {
    try {
      const res = await fetch("http://localhost:5000/action-logs");
      const logs = await res.json();
      setActionLogs(Array.isArray(logs) ? logs : []);
    } catch (error) {
      console.error("Failed to fetch action logs:", error);
    }
  };

  const clearActionLogs = async () => {
    try {
      await fetch("http://localhost:5000/clear-logs", { method: "POST" });
      setActionLogs([]);
    } catch (error) {
      console.error("Failed to clear action logs:", error);
    }
  };

  // const logManualAction = async (actionType: string, description: string, coordinates?: [number, number], textContent?: string) => {
  //   try {
  //     await invoke<string>("log_manual_action", {
  //       actionType,
  //       description,
  //       coordinates,
  //       textContent,
  //     });
  //     // Refresh logs after adding manual action
  //     await fetchActionLogs();
  //   } catch (error) {
  //     console.error("Failed to log manual action:", error);
  //   }
  // };

  const toggleActionLogs = () => {
    setShowActionLogs(prev => !prev);
    if (!showActionLogs) {
      fetchActionLogs();
    }
  };

  // Auto-refresh logs when automation is active
  useEffect(() => {
    if (automationState.isActive && showActionLogs) {
      const interval = setInterval(fetchActionLogs, 2000); // Refresh every 2 seconds
      return () => clearInterval(interval);
    }
  }, [automationState.isActive, showActionLogs]);

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString();
  };

  return (
    <div className="app" style={{ pointerEvents: 'none' }}>
      {(() => {
        const dockToRender = isDraggingNotch ? getPreviewDock() : notchDock;
        return (
      <div
        className={`notch ${dockToRender}`}
        style={{ pointerEvents: 'auto' }}
        onMouseEnter={() => (window as any).overlayAPI?.setInteractive(true)}
        onMouseLeave={() => { if (!isDraggingNotch) (window as any).overlayAPI?.setInteractive(false); }}
        onMouseDown={onNotchDragStart}
      >
        <div className="title">Desktop Assistant</div>
        <div className="controls">
          <button
            className="pill-button"
            onClick={() => {
              setPanelOpen((prev) => {
                const next = !prev;
                if (next) setPanelOpaque(true);
                return next;
              });
            }}
          >
            {panelOpen ? "Hide" : "Show"}
          </button>
          <div
            className="drag-handle"
            title="Drag to move (snaps left/center/right)"
            onMouseDown={onNotchDragStart}
          />
          {automationState.isActive && (
            <>
              {!automationState.isAutomatic && (
                <button onClick={continueAutomation} className="automation-button" title="Continue Automation">
                  ▶️ Next Step
                </button>
              )}
              <button 
                onClick={toggleAutomaticMode} 
                className={automationState.isAutomatic ? "auto-mode-active" : "auto-mode-inactive"}
                title={automationState.isAutomatic ? "Switch to Manual Mode" : "Switch to Automatic Mode"}
              >
                {automationState.isAutomatic ? "🤖 AUTO" : "👤 MANUAL"}
              </button>
              {automationState.isAutomatic && (
                <div className="delay-controls">
                  <button 
                    onClick={() => adjustAutoDelay(automationState.autoDelay - 1)} 
                    className="delay-button"
                    title="Decrease delay"
                  >
                    -
                  </button>
                  <span className="delay-display">{automationState.autoDelay}s</span>
                  <button 
                    onClick={() => adjustAutoDelay(automationState.autoDelay + 1)} 
                    className="delay-button"
                    title="Increase delay"
                  >
                    +
                  </button>
                  {countdown > 0 && (
                    <span className="countdown-display">Next: {countdown}s</span>
                  )}
                </div>
              )}
              <button onClick={stopAutomation} className="stop-button" title="Stop Automation">
                🛑 Stop
              </button>
            </>
          )}
          <button className="pill-button" onClick={manualResize} title="Manual Resize">📏</button>
          <button onClick={toggleActionLogs} className={showActionLogs ? "action-log-button active" : "action-log-button"} title="Action Logs">
            📋
          </button>
        </div>
      </div>
        );})()}

      {panelOpen && (() => { const dockToRender = isDraggingNotch ? getPreviewDock() : notchDock; return (
      <div
        className={`panel${panelOpaque ? ' opaque' : ''}${dockToRender === 'center' ? '' : ' vertical ' + dockToRender}`}
        style={{ pointerEvents: 'auto' }}
        onMouseEnter={() => (window as any).overlayAPI?.setInteractive(true)}
        onMouseLeave={() => { if (!isDraggingNotch) (window as any).overlayAPI?.setInteractive(false); }}
        onFocusCapture={() => setPanelOpaque(true)}
        onBlurCapture={() => setPanelOpaque(false)}
      >
        <div className="chat-header">
          <h1>🤖 Desktop Assistant</h1>
          <div className="header-controls"></div>
        </div>
        <div className="chat-messages">
        {messages.map((message, index) => (
          <div key={index} className={`message ${message.sender}`}>
            {message.hasImage && message.imageData && (
              <div className="message-image">
                <img src={`data:image/png;base64,${message.imageData}`} alt="Captured screen" />
              </div>
            )}
            <div className="message-text">{message.text}</div>
            {(message.prompt || (message.text && message.text.length > 0)) && (
              <details className="prompt-details">
                <summary>Details</summary>
                {message.prompt && (
                  <>
                    <div className="prompt-label">Prompt</div>
                    <pre className="prompt-block">{message.prompt}</pre>
                  </>
                )}
                {message.text && (
                  <>
                    <div className="prompt-label">Answer</div>
                    <pre className="prompt-block">{message.text}</pre>
                  </>
                )}
              </details>
            )}
          </div>
        ))}
        {isLoading && (
          <div className="message bot loading">
            <div className="loading-dots">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        )}
        </div>

      {showActionLogs && (
        <div className="action-log-panel">
          <div className="action-log-header">
            <h3>📋 Action Log</h3>
            <div className="action-log-controls">
              <button onClick={fetchActionLogs} className="refresh-button" title="Refresh Logs">
                🔄
              </button>
              <button onClick={clearActionLogs} className="clear-button" title="Clear Logs">
                🗑️
              </button>
            </div>
          </div>
          <div className="action-log-content">
            {actionLogs.length === 0 ? (
              <div className="no-logs">No actions logged yet</div>
            ) : (
              actionLogs.slice().reverse().map((log) => (
                <div key={log.id} className={`log-entry ${log.success ? 'success' : 'error'}`}>
                  <div className="log-header">
                    <span className="log-type">{log.action_type}</span>
                    <span className="log-time">{formatTimestamp(log.timestamp)}</span>
                  </div>
                  <div className="log-description">{log.description}</div>
                  {log.coordinates && (
                    <div className="log-coordinates">
                      📍 Coordinates: ({log.coordinates[0]}, {log.coordinates[1]})
                    </div>
                  )}
                  {log.text_content && (
                    <div className="log-text-content">
                      💬 Text: {log.text_content}
                    </div>
                  )}
                  {log.error_message && (
                    <div className="log-error">
                      ❌ Error: {log.error_message}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {capturedImage && (
        <div className="image-preview">
          <div className="image-preview-header">
            <span>📷 Screen captured</span>
            <button onClick={clearImage} className="clear-image">✕</button>
          </div>
          <img src={`data:image/png;base64,${capturedImage}`} alt="Captured screen" />
        </div>
      )}

      <div className="input-container">
        <div className="input-row">
          <button onClick={captureScreen} className="capture-button">
            📷
          </button>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onFocus={() => setPanelOpaque(true)}
            onBlur={() => setPanelOpaque(false)}
            onKeyPress={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                if (e.ctrlKey) {
                  startAutomation();
                } else {
                  sendMessage();
                }
              }
            }}
            placeholder={automationState.isActive 
              ? `🤖 ${automationState.isAutomatic ? 'AUTO' : 'MANUAL'}: ${automationState.goal} (Step ${automationState.stepCount})`
              : "Type message... (Ctrl+Enter for automation)"}
            className="message-input"
            disabled={automationState.isActive}
          />
          {!automationState.isActive && (
            <button onClick={startAutomation} className="automation-start-button" title="Start Automation (Ctrl+Enter)">
              🤖
            </button>
          )}
          <button onClick={sendMessage} className="send-button" disabled={automationState.isActive}>
            ➤
          </button>
        </div>
      </div>
      </div>
      );})()}

      {isDraggingNotch && (
        <>
          <div className={`notch preview ${getPreviewDock()}`} />
          {panelOpen && (
            <div className={`panel preview ${getPreviewDock() === 'center' ? '' : 'vertical ' + getPreviewDock()}`} />
          )}
        </>
      )}
    </div>
  );
}

export default App;
