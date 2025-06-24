import { useState, useEffect, useRef } from "react";
import { invoke } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { LogicalSize, LogicalPosition } from "@tauri-apps/api/dpi";
import { availableMonitors, primaryMonitor } from "@tauri-apps/api/window";
import "./App.css";

interface Message {
  text: string;
  sender: "user" | "bot";
  hasImage?: boolean;
  imageData?: string;
}

function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [capturedImage, setCapturedImage] = useState<string | null>(null);
  const [isExpanded, setIsExpanded] = useState(false);

  // Simple auto-resize function
  const autoResize = async () => {
    if (!isExpanded) return;
    
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
      
      // Position at bottom of screen
      const monitor = await primaryMonitor();
      if (monitor) {
        const x = (monitor.size.width - 800) / 2;
        const y = monitor.size.height - finalHeight - 40;
        await window.setPosition(new LogicalPosition(x, Math.max(0, y)));
      }
      
    } catch (error) {
      console.error("Auto-resize error:", error);
    }
  };

  // Trigger resize when content changes
  useEffect(() => {
    if (isExpanded) {
      const timer = setTimeout(autoResize, 100);
      return () => clearTimeout(timer);
    }
  }, [messages.length, capturedImage, isLoading, isExpanded]);

  // Manual resize for testing
  const manualResize = () => {
    console.log("Manual resize triggered");
    autoResize();
  };

  const toggleExpanded = async () => {
    try {
      const window = getCurrentWindow();
      const newExpanded = !isExpanded;
      setIsExpanded(newExpanded);

      if (newExpanded) {
        // Expand and auto-resize
        setTimeout(autoResize, 50);
      } else {
        // Minimize to bar
        const monitor = await primaryMonitor();
        if (monitor) {
          await window.setSize(new LogicalSize(800, 60));
          const x = (monitor.size.width - 800) / 2;
          const y = monitor.size.height - 70;
          await window.setPosition(new LogicalPosition(x, y));
        }
      }
    } catch (error) {
      console.error("Toggle error:", error);
    }
  };

  const captureScreen = async () => {
    try {
      const imageData = await invoke<string>("capture_screen");
      setCapturedImage(imageData);
      if (!isExpanded) {
        await toggleExpanded();
      }
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

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const clearImage = () => {
    setCapturedImage(null);
  };

  return (
    <div className="app">
      {isExpanded ? (
        <>
          {/* Expanded Chat View */}
          <div className="chat-header">
            <h1>🤖 Desktop Assistant</h1>
            <div className="header-controls">
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
              <button onClick={toggleExpanded} className="minimize-button">
                ➖
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
                onKeyPress={handleKeyPress}
                placeholder="Type your message..."
                className="message-input"
              />
              <button onClick={sendMessage} className="send-button">
                ➤
              </button>
            </div>
          </div>
        </>
      ) : (
        /* Minimized Bar View */
        <div className="minimized-bar">
          <button onClick={captureScreen} className="bar-capture-button">
            📷
          </button>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                if (input.trim()) {
                  toggleExpanded().then(() => sendMessage());
                } else {
                  toggleExpanded();
                }
              }
            }}
            placeholder="Ask anything..."
            className="bar-input"
            onFocus={toggleExpanded}
          />
          <button 
            onClick={() => {
              if (input.trim()) {
                toggleExpanded().then(() => sendMessage());
              } else {
                toggleExpanded();
              }
            }} 
            className="bar-send-button"
          >
            ➤
          </button>
        </div>
      )}
    </div>
  );
}

export default App;
