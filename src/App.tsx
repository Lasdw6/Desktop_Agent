import { useState, useEffect, useCallback } from "react";
import { invoke } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { LogicalSize, LogicalPosition } from "@tauri-apps/api/dpi";
import { primaryMonitor } from "@tauri-apps/api/window";
import "./App.css";

interface Message {
  text: string;
  sender: "user" | "bot";
  hasImage?: boolean;
  imageData?: string;
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

function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [capturedImage, setCapturedImage] = useState<string | null>(null);
  const [actionLogs, setActionLogs] = useState<ActionLog[]>([]);
  const [showActionLogs, setShowActionLogs] = useState(false);

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
  const autoResize = async () => {
    try {
      const window = getCurrentWindow();
      
      // Calculate height based on content
      let height = 280; // Base height (header + input + padding)
      height += messages.length * 100; // 100px per message
      if (capturedImage) height += 180; // Image preview
      if (isLoading) height += 60; // Loading indicator
      
      // Apply constraints
      const finalHeight = Math.max(Math.min(height, 900), 400);
      
      console.log(`Auto-resize: ${messages.length} messages, image: ${!!capturedImage}, height: ${finalHeight}`);
      
      await window.setSize(new LogicalSize(800, finalHeight));
      
      // Center the window
      const monitor = await primaryMonitor();
      if (monitor) {
        const x = (monitor.size.width - 800) / 2;
        const y = (monitor.size.height - finalHeight) / 2;
        await window.setPosition(new LogicalPosition(x, Math.max(0, y)));
      }
      
    } catch (error) {
      console.error("Auto-resize error:", error);
    }
  };

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
      const responseJson = await invoke<string>("continue_automation", {
        goal: automationState.goal,
        previousInstruction: automationState.lastInstruction,
        stepCount: automationState.stepCount,
      });

      const response: AutomationResponse = JSON.parse(responseJson);

      const botMessage: Message = {
        text: `Step ${automationState.stepCount + 1}: ${response.instruction}`,
        sender: "bot",
        hasImage: !!response.screenshot,
        imageData: response.screenshot,
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
  const manualResize = () => {
    console.log("Manual resize triggered");
    autoResize();
  };



  const captureScreen = async () => {
    try {
      const imageData = await invoke<string>("capture_screen");
      setCapturedImage(imageData);
    } catch (error) {
      console.error("Capture error:", error);
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
        response = await invoke<string>("chat_with_vision", {
          message: input || "What do you see in this image?",
          imageData: capturedImage,
        });
        setCapturedImage(null);
      } else {
        response = await invoke<string>("chat_with_gpt", { message: input });
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
      const responseJson = await invoke<string>("start_automation", { goal });
      const response: AutomationResponse = JSON.parse(responseJson);
      
      const botMessage: Message = {
        text: `Step 1: ${response.instruction}`,
        sender: "bot",
        hasImage: !!response.screenshot,
        imageData: response.screenshot,
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
      const logs = await invoke<ActionLog[]>("get_action_logs");
      setActionLogs(logs);
    } catch (error) {
      console.error("Failed to fetch action logs:", error);
    }
  };

  const clearActionLogs = async () => {
    try {
      await invoke<string>("clear_action_logs");
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
    <div className="app">
      <div className="chat-header">
        <h1>🤖 Desktop Assistant</h1>
        <div className="header-controls">
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
          <button onClick={manualResize} className="resize-button" title="Manual Resize">
            📏
          </button>
          <button onClick={async () => {
            try {
              const result = await invoke<string>("test_env");
              alert(result);
            } catch (error) {
              alert(`Test failed: ${error}`);
            }
          }} className="resize-button" title="Test API Key">
            🔑
          </button>
          <button onClick={toggleActionLogs} className={showActionLogs ? "action-log-button active" : "action-log-button"} title="Action Logs">
            📋
          </button>
        </div>
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
  );
}

export default App;
