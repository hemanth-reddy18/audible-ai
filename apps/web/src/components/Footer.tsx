export default function Footer() {
  return (
    <footer className="fixed bottom-0 left-0 right-0 bg-background/80 backdrop-blur-md border-t border-border/50 py-3 px-6 z-10">
      <div className="flex justify-between items-center text-xs text-muted-foreground max-w-7xl mx-auto">
        <div>
          <span>Audible AI Platform</span>
          <span className="mx-2 text-border">|</span>
          <span className="text-[11px] opacity-75">Production Voice Runtime</span>
        </div>
        <div className="flex items-center gap-4">
          <a
            href="https://github.com/audible-ai/audible-ai"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-foreground transition-colors"
          >
            GitHub
          </a>
          <span className="text-border">|</span>
          <a
            href="https://github.com/audible-ai/audible-ai/blob/main/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-foreground transition-colors"
          >
            Documentation
          </a>
        </div>
      </div>
    </footer>
  );
}
