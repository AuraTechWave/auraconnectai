# AI Analytics Assistant - Frontend Integration Guide

This guide provides examples for integrating the AI Analytics Assistant chat interface into your frontend application.

## WebSocket Connection

### JavaScript/TypeScript Example

```typescript
// analytics-chat-client.ts

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'error';
  content: string;
  type: 'text' | 'query_result' | 'chart' | 'table';
  timestamp: string;
  metadata?: any;
}

interface QueryResult {
  query_id: string;
  status: string;
  summary: string;
  data?: ChartData | TableData;
  insights?: string[];
}

class AnalyticsChatClient {
  private ws: WebSocket | null = null;
  private token: string;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private messageHandlers: Map<string, (data: any) => void> = new Map();

  constructor(token: string) {
    this.token = token;
  }

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      const wsUrl = `ws://localhost:8000/analytics/ai-assistant/chat?token=${this.token}`;
      
      this.ws = new WebSocket(wsUrl);
      
      this.ws.onopen = () => {
        console.log('Connected to AI Analytics Assistant');
        this.reconnectAttempts = 0;
        resolve();
      };
      
      this.ws.onmessage = (event) => {
        this.handleMessage(JSON.parse(event.data));
      };
      
      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        reject(error);
      };
      
      this.ws.onclose = () => {
        console.log('Disconnected from AI Analytics Assistant');
        this.attemptReconnect();
      };
    });
  }

  private handleMessage(message: any): void {
    const handler = this.messageHandlers.get(message.type);
    if (handler) {
      handler(message.data);
    }
  }

  private attemptReconnect(): void {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      console.log(`Reconnecting... Attempt ${this.reconnectAttempts}`);
      setTimeout(() => this.connect(), 3000);
    }
  }

  sendMessage(message: string): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'chat',
        message: message
      }));
    }
  }

  onMessage(type: string, handler: (data: any) => void): void {
    this.messageHandlers.set(type, handler);
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}
```

## React Component Example

```tsx
// AnalyticsChatWidget.tsx

import React, { useState, useEffect, useRef } from 'react';
import { AnalyticsChatClient } from './analytics-chat-client';

interface ChatWidgetProps {
  token: string;
  onClose?: () => void;
}

const AnalyticsChatWidget: React.FC<ChatWidgetProps> = ({ token, onClose }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [suggestedQuestions, setSuggestedQuestions] = useState<string[]>([]);
  
  const chatClient = useRef<AnalyticsChatClient | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Initialize chat client
    chatClient.current = new AnalyticsChatClient(token);
    
    // Set up message handlers
    chatClient.current.onMessage('connected', (data) => {
      setIsConnected(true);
      if (data.capabilities) {
        console.log('Assistant capabilities:', data.capabilities);
      }
    });
    
    chatClient.current.onMessage('chat', (data) => {
      setIsTyping(false);
      
      // Add assistant message
      const newMessage: ChatMessage = data.message;
      setMessages(prev => [...prev, newMessage]);
      
      // Update suggested questions
      if (data.suggested_questions) {
        setSuggestedQuestions(data.suggested_questions);
      }
      
      // Handle query results
      if (data.query_result) {
        handleQueryResult(data.query_result);
      }
    });
    
    chatClient.current.onMessage('typing', (data) => {
      setIsTyping(data.is_typing);
    });
    
    chatClient.current.onMessage('error', (data) => {
      console.error('Chat error:', data.message);
      // Show error to user
    });
    
    // Connect to WebSocket
    chatClient.current.connect().catch(console.error);
    
    // Cleanup
    return () => {
      if (chatClient.current) {
        chatClient.current.disconnect();
      }
    };
  }, [token]);

  useEffect(() => {
    // Scroll to bottom when new messages arrive
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSendMessage = (): void => {
    if (!inputValue.trim() || !chatClient.current) return;
    
    // Add user message
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: inputValue,
      type: 'text',
      timestamp: new Date().toISOString()
    };
    
    setMessages(prev => [...prev, userMessage]);
    chatClient.current.sendMessage(inputValue);
    setInputValue('');
  };

  const handleQueryResult = (result: QueryResult): void => {
    if (result.data) {
      // Render chart or table based on data type
      console.log('Query result:', result);
      // Implementation depends on your charting library
    }
  };

  const handleSuggestedQuestion = (question: string): void => {
    setInputValue(question);
  };

  return (
    <div className="chat-widget">
      <div className="chat-header">
        <h3>Analytics Assistant</h3>
        <button onClick={onClose}>×</button>
      </div>
      
      <div className="chat-messages">
        {messages.map((msg) => (
          <div key={msg.id} className={`message ${msg.role}`}>
            <div className="message-content">
              {msg.content}
            </div>
            {msg.type === 'query_result' && (
              <div className="query-result">
                {/* Render charts/tables here */}
              </div>
            )}
          </div>
        ))}
        
        {isTyping && (
          <div className="typing-indicator">
            <span></span>
            <span></span>
            <span></span>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>
      
      {suggestedQuestions.length > 0 && (
        <div className="suggested-questions">
          {suggestedQuestions.map((question, idx) => (
            <button
              key={idx}
              onClick={() => handleSuggestedQuestion(question)}
              className="suggestion-chip"
            >
              {question}
            </button>
          ))}
        </div>
      )}
      
      <div className="chat-input">
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
          placeholder="Ask about your analytics..."
          disabled={!isConnected}
        />
        <button onClick={handleSendMessage} disabled={!isConnected}>
          Send
        </button>
      </div>
    </div>
  );
};

export default AnalyticsChatWidget;
```

## Vue.js Component Example

```vue
<!-- AnalyticsChatWidget.vue -->

<template>
  <div class="analytics-chat-widget">
    <div class="chat-header">
      <h3>Analytics Assistant</h3>
      <button @click="$emit('close')" class="close-btn">×</button>
    </div>
    
    <div class="chat-messages" ref="messagesContainer">
      <div
        v-for="message in messages"
        :key="message.id"
        :class="['message', `message-${message.role}`]"
      >
        <div class="message-content">{{ message.content }}</div>
        
        <!-- Render query results -->
        <div v-if="message.queryResult" class="query-result">
          <component
            :is="getResultComponent(message.queryResult)"
            :data="message.queryResult.data"
          />
        </div>
      </div>
      
      <!-- Typing indicator -->
      <div v-if="isTyping" class="typing-indicator">
        <span></span>
        <span></span>
        <span></span>
      </div>
    </div>
    
    <!-- Suggested questions -->
    <div v-if="suggestedQuestions.length > 0" class="suggested-questions">
      <button
        v-for="(question, index) in suggestedQuestions"
        :key="index"
        @click="selectSuggestion(question)"
        class="suggestion-chip"
      >
        {{ question }}
      </button>
    </div>
    
    <!-- Input area -->
    <div class="chat-input">
      <input
        v-model="inputMessage"
        @keypress.enter="sendMessage"
        placeholder="Ask about your analytics..."
        :disabled="!isConnected"
      />
      <button @click="sendMessage" :disabled="!isConnected">
        Send
      </button>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted, nextTick } from 'vue';
import { AnalyticsChatClient } from './analytics-chat-client';

export default {
  name: 'AnalyticsChatWidget',
  props: {
    token: {
      type: String,
      required: true
    }
  },
  setup(props) {
    const messages = ref([]);
    const inputMessage = ref('');
    const isTyping = ref(false);
    const isConnected = ref(false);
    const suggestedQuestions = ref([]);
    const messagesContainer = ref(null);
    
    let chatClient = null;
    
    onMounted(async () => {
      // Initialize and connect
      chatClient = new AnalyticsChatClient(props.token);
      
      // Set up handlers
      chatClient.onMessage('connected', (data) => {
        isConnected.value = true;
      });
      
      chatClient.onMessage('chat', (data) => {
        isTyping.value = false;
        messages.value.push(data.message);
        
        if (data.suggested_questions) {
          suggestedQuestions.value = data.suggested_questions;
        }
        
        scrollToBottom();
      });
      
      chatClient.onMessage('typing', (data) => {
        isTyping.value = data.is_typing;
      });
      
      // Connect
      await chatClient.connect();
    });
    
    onUnmounted(() => {
      if (chatClient) {
        chatClient.disconnect();
      }
    });
    
    const sendMessage = () => {
      if (!inputMessage.value.trim() || !chatClient) return;
      
      // Add user message
      messages.value.push({
        id: Date.now().toString(),
        role: 'user',
        content: inputMessage.value,
        type: 'text',
        timestamp: new Date().toISOString()
      });
      
      chatClient.sendMessage(inputMessage.value);
      inputMessage.value = '';
      scrollToBottom();
    };
    
    const selectSuggestion = (question) => {
      inputMessage.value = question;
    };
    
    const scrollToBottom = async () => {
      await nextTick();
      if (messagesContainer.value) {
        messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
      }
    };
    
    const getResultComponent = (result) => {
      // Return appropriate component based on result type
      if (result.data?.type === 'chart') return 'ChartComponent';
      if (result.data?.type === 'table') return 'TableComponent';
      return 'div';
    };
    
    return {
      messages,
      inputMessage,
      isTyping,
      isConnected,
      suggestedQuestions,
      messagesContainer,
      sendMessage,
      selectSuggestion,
      getResultComponent
    };
  }
};
</script>

<style scoped>
.analytics-chat-widget {
  display: flex;
  flex-direction: column;
  height: 600px;
  width: 400px;
  border: 1px solid #ddd;
  border-radius: 8px;
  overflow: hidden;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  background: #f5f5f5;
  border-bottom: 1px solid #ddd;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
}

.message {
  margin-bottom: 1rem;
}

.message-user {
  text-align: right;
}

.message-user .message-content {
  background: #007bff;
  color: white;
  display: inline-block;
  padding: 0.5rem 1rem;
  border-radius: 18px;
  max-width: 80%;
}

.message-assistant .message-content {
  background: #f1f1f1;
  display: inline-block;
  padding: 0.5rem 1rem;
  border-radius: 18px;
  max-width: 80%;
}

.typing-indicator {
  display: flex;
  align-items: center;
  margin: 0.5rem 0;
}

.typing-indicator span {
  height: 8px;
  width: 8px;
  background: #999;
  border-radius: 50%;
  margin: 0 2px;
  animation: typing 1.4s infinite;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing {
  0%, 60%, 100% {
    opacity: 0.3;
  }
  30% {
    opacity: 1;
  }
}

.suggested-questions {
  padding: 0.5rem;
  border-top: 1px solid #eee;
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.suggestion-chip {
  padding: 0.25rem 0.75rem;
  border: 1px solid #ddd;
  border-radius: 16px;
  background: white;
  cursor: pointer;
  font-size: 0.875rem;
}

.suggestion-chip:hover {
  background: #f5f5f5;
}

.chat-input {
  display: flex;
  padding: 1rem;
  border-top: 1px solid #ddd;
}

.chat-input input {
  flex: 1;
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  margin-right: 0.5rem;
}

.chat-input button {
  padding: 0.5rem 1rem;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.chat-input button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
```

## CSS Styles

```css
/* analytics-chat.css */

.chat-widget {
  position: fixed;
  bottom: 20px;
  right: 20px;
  width: 400px;
  height: 600px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
  display: flex;
  flex-direction: column;
  z-index: 1000;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  background: #f8f9fa;
  border-bottom: 1px solid #dee2e6;
  border-radius: 8px 8px 0 0;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
  background: #ffffff;
}

.message {
  margin-bottom: 1rem;
  animation: fadeIn 0.3s ease-in;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.message.user {
  text-align: right;
}

.message.user .message-content {
  background: #007bff;
  color: white;
  display: inline-block;
  padding: 0.75rem 1rem;
  border-radius: 18px 18px 4px 18px;
  max-width: 80%;
  word-wrap: break-word;
}

.message.assistant .message-content {
  background: #f1f3f5;
  color: #212529;
  display: inline-block;
  padding: 0.75rem 1rem;
  border-radius: 18px 18px 18px 4px;
  max-width: 80%;
  word-wrap: break-word;
}

.message.error .message-content {
  background: #f8d7da;
  color: #721c24;
  border-left: 4px solid #f5c6cb;
}

.typing-indicator {
  display: flex;
  align-items: center;
  padding: 0.5rem 1rem;
}

.typing-indicator span {
  height: 8px;
  width: 8px;
  background: #6c757d;
  border-radius: 50%;
  margin: 0 2px;
  animation: typing 1.4s infinite;
}

.suggested-questions {
  padding: 0.75rem;
  background: #f8f9fa;
  border-top: 1px solid #dee2e6;
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.suggestion-chip {
  padding: 0.375rem 0.75rem;
  background: white;
  border: 1px solid #dee2e6;
  border-radius: 20px;
  font-size: 0.875rem;
  cursor: pointer;
  transition: all 0.2s;
}

.suggestion-chip:hover {
  background: #007bff;
  color: white;
  border-color: #007bff;
}

.chat-input {
  display: flex;
  padding: 1rem;
  background: #f8f9fa;
  border-top: 1px solid #dee2e6;
  border-radius: 0 0 8px 8px;
}

.chat-input input {
  flex: 1;
  padding: 0.5rem 1rem;
  border: 1px solid #ced4da;
  border-radius: 20px;
  outline: none;
  font-size: 0.875rem;
}

.chat-input input:focus {
  border-color: #007bff;
}

.chat-input button {
  margin-left: 0.5rem;
  padding: 0.5rem 1.5rem;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 20px;
  cursor: pointer;
  font-size: 0.875rem;
  transition: background 0.2s;
}

.chat-input button:hover:not(:disabled) {
  background: #0056b3;
}

.chat-input button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Query result styles */
.query-result {
  margin-top: 0.5rem;
  padding: 1rem;
  background: #f8f9fa;
  border-radius: 8px;
}

.query-result .chart-container {
  width: 100%;
  height: 200px;
}

.query-result .table-container {
  max-height: 300px;
  overflow-y: auto;
}

.query-result table {
  width: 100%;
  border-collapse: collapse;
}

.query-result th,
.query-result td {
  padding: 0.5rem;
  text-align: left;
  border-bottom: 1px solid #dee2e6;
}

.query-result th {
  background: #e9ecef;
  font-weight: 600;
}

/* Mobile responsive */
@media (max-width: 768px) {
  .chat-widget {
    width: 100%;
    height: 100%;
    bottom: 0;
    right: 0;
    border-radius: 0;
  }
}
```

## Integration Steps

1. **Install Dependencies**
   ```bash
   npm install --save chart.js react-chartjs-2  # For React
   npm install --save chart.js vue-chartjs     # For Vue
   ```

2. **Set Up Authentication**
   - Obtain authentication token from your backend
   - Pass token to the chat component

3. **Initialize Chat Widget**
   ```javascript
   // In your main app
   const token = await getAuthToken();
   
   // React
   <AnalyticsChatWidget token={token} />
   
   // Vue
   <analytics-chat-widget :token="token" />
   ```

4. **Handle Chart/Table Rendering**
   - Implement chart components using your preferred library
   - Parse query results and render appropriate visualizations

5. **Customize Styling**
   - Modify CSS to match your application's design system
   - Add dark mode support if needed

## Security Considerations

1. **Token Management**
   - Store tokens securely
   - Implement token refresh logic
   - Clear tokens on logout

2. **Input Validation**
   - Frontend validation is for UX only
   - Backend handles security validation

3. **Content Security**
   - Sanitize any HTML content
   - Use trusted chart libraries

## Performance Optimization

1. **Lazy Loading**
   - Load chat widget on demand
   - Code-split chart libraries

2. **Message Pagination**
   - Implement virtual scrolling for long conversations
   - Load history on demand

3. **WebSocket Reconnection**
   - Implement exponential backoff
   - Queue messages during disconnection

## Example Usage Scenarios

### Quick Analytics Query
```javascript
// User types: "Show me today's sales"
// Assistant responds with sales summary and chart
```

### Drill-Down Analysis
```javascript
// User: "What are the top selling products?"
// Assistant: Shows product performance table
// User: "Show me the trend for Product A"
// Assistant: Shows line chart for Product A sales
```

### Comparison Queries
```javascript
// User: "Compare this week to last week"
// Assistant: Shows comparison charts and insights
```

This integration guide provides the foundation for implementing the AI Analytics Assistant chat interface in your frontend application. Customize and extend based on your specific requirements.