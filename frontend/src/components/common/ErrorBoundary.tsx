"use client";

import { AlertTriangle } from "lucide-react";
import { Component, ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: (err: Error, reset: () => void) => ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: unknown) {
    // eslint-disable-next-line no-console
    console.error("[ErrorBoundary]", error, info);
  }

  private reset = () => {
    this.setState({ error: null });
  };

  render() {
    if (this.state.error) {
      const { fallback } = this.props;
      if (fallback) return fallback(this.state.error, this.reset);
      return (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-destructive" />
              <CardTitle>頁面發生錯誤</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <pre className="overflow-auto rounded bg-muted p-2 text-xs">
              {this.state.error.message}
            </pre>
            <Button variant="outline" onClick={this.reset}>
              重試
            </Button>
          </CardContent>
        </Card>
      );
    }
    return this.props.children;
  }
}
