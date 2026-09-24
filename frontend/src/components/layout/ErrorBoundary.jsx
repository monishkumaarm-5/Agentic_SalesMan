import { Component } from 'react'

export default class ErrorBoundary extends Component {
  state = { error: null }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('[ui] render error', error, info.componentStack)
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div role="alert" className="crash">
        <h2>Something went wrong</h2>
        <p>The page hit an unexpected error. Your conversation is saved.</p>
        <button type="button" className="btn btn-primary" onClick={() => this.setState({ error: null })}>
          Try again
        </button>
      </div>
    )
  }
}
