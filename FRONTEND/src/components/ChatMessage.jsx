import ReactMarkdown from 'react-markdown'

function ChatMessage({ role, content, isError }) {
  const isUser = role === 'user'

  return (
    <div className={`message-row ${isUser ? 'from-user' : 'from-assistant'}`}>
      <div className={`avatar ${isUser ? 'user' : 'assistant'}`}>
        {isUser ? 'You' : 'AI'}
      </div>
      <div className={`bubble ${isError ? 'error' : ''}`}>
        {isUser ? <p>{content}</p> : <ReactMarkdown>{content}</ReactMarkdown>}
      </div>
    </div>
  )
}

export default ChatMessage
