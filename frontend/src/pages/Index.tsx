import { useState, useRef } from "react";
import { Upload, Download, ImagePlus, Sliders } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { useToast } from "@/hooks/use-toast";

interface UpscaleResult {
  url: string;
  filename: string;
}

interface UpscaleFailure {
  source: string;
  error: string;
}

const Index = () => {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [scale, setScale] = useState("4");
  const [model, setModel] = useState("realesrgan-x4plus");
  const [faceEnhance, setFaceEnhance] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [results, setResults] = useState<UpscaleResult[]>([]);
  const [failures, setFailures] = useState<UpscaleFailure[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { toast } = useToast();

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const files = Array.from(e.dataTransfer.files).filter(file => 
      file.type.startsWith("image/")
    );
    if (files.length > 0) {
      setSelectedFiles(files);
      toast({
        title: "Files selected",
        description: `${files.length} image(s) ready to upscale`,
      });
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (files.length > 0) {
      setSelectedFiles(files);
      toast({
        title: "Files selected",
        description: `${files.length} image(s) ready to upscale`,
      });
    }
  };

  async function handleUpscale() {
    if (selectedFiles.length === 0) return;
    setIsProcessing(true);
    setFailures([]);

    const fd = new FormData();

    // 1) A backend 'images' kulccsal várja a file-listát (NEM: files/file)
    selectedFiles.forEach(f => {
      fd.append("images", f, f.name);
    });

    // 2) A backend 'face' mezőt olvas (NEM: face_enhance)
    const scl = Number(scale) || 4;
    fd.append("scale", String(scl));
    fd.append("model", model);
    fd.append("face", faceEnhance ? "1" : "0");

    try {
      const res = await fetch("/api/upscale", { method: "POST", body: fd });
      const text = await res.text();
      if (!res.ok) throw new Error(`HTTP ${res.status} – ${text || "nincs üzenet"}`);

      // 3) A backend képenként jelzi, hogy sikerült-e
      type ApiItem = {
        source: string;
        ok: boolean;
        error?: string | null;
        url?: string;
        filename?: string;
      };
      const payload = JSON.parse(text) as { ok: boolean; results: ApiItem[] };
      const list = payload.results ?? [];

      const ts = Date.now();
      const done = list.filter(d => d.ok && d.url);
      const bad = list.filter(d => !d.ok);

      setResults(done.map(d => ({
        url: `${d.url}?t=${ts}`,
        filename: d.filename ?? d.source,
      })));
      setFailures(bad.map(d => ({
        source: d.source,
        error: d.error ?? "Ismeretlen hiba.",
      })));

      // Az arcjavítás külön hibázhat úgy is, hogy a felnagyítás sikerült
      const warned = list.filter(d => d.ok && d.error);

      if (bad.length === 0) {
        toast({
          title: "Upscaling kész!",
          description: warned.length
            ? `${done.length} kép feldolgozva, ${warned.length} figyelmeztetéssel.`
            : `${done.length} kép feldolgozva.`,
        });
      } else if (done.length === 0) {
        toast({
          title: "Egyik kép sem sikerült",
          description: bad[0].error ?? "Nézd meg az upscale.log fájlt.",
          variant: "destructive",
        });
      } else {
        toast({
          title: `${done.length} kész, ${bad.length} hibás`,
          description: "A hibás képek a lista alatt vannak felsorolva.",
          variant: "destructive",
        });
      }
    } catch (e: any) {
      toast({ title: "Hiba az upscalingnél", description: e.message, variant: "destructive" });
    } finally {
      setIsProcessing(false);
    }
  }

  return (
    <div className="min-h-screen minimal-gradient">
      <div className="container mx-auto px-4 py-12 md:py-20 max-w-5xl">
        {/* Header */}
        <header className="text-center mb-16 md:mb-20 animate-fade-in">
          <h1 className="text-5xl md:text-7xl font-extralight tracking-tighter mb-4 text-foreground">
            Image Upscaler
          </h1>
          <p className="text-muted-foreground text-base md:text-lg font-light tracking-wide max-w-xl mx-auto">
            Professional AI-powered enhancement
          </p>
        </header>

        {/* Controls */}
        <div className="mb-10 animate-scale-in">
          <Card className="p-6 md:p-8 elegant-shadow elegant-border bg-card/50 backdrop-blur-sm">
            <div className="flex items-center gap-3 mb-6">
              <Sliders className="w-5 h-5 text-foreground/70" />
              <h2 className="text-sm font-medium uppercase tracking-wider text-foreground/70">
                Configuration
              </h2>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="space-y-3">
                <Label htmlFor="scale" className="text-sm font-light text-foreground/80">
                  Scale Factor
                </Label>
                <Select value={scale} onValueChange={setScale}>
                  <SelectTrigger id="scale" className="bg-secondary/50 border-border/50 h-11">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="2">2× Enhancement</SelectItem>
                    <SelectItem value="3">3× Enhancement</SelectItem>
                    <SelectItem value="4">4× Enhancement</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-3">
                <Label htmlFor="model" className="text-sm font-light text-foreground/80">
                  AI Model
                </Label>
                <Select value={model} onValueChange={setModel}>
                  <SelectTrigger id="model" className="bg-secondary/50 border-border/50 h-11">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="realesrgan-x4plus">General Purpose</SelectItem>
                    <SelectItem value="realesrgan-x4plus-anime">Anime & Art</SelectItem>
                    <SelectItem value="realesrnet-x4plus">RealESRNet</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-end">
                <div className="flex items-center space-x-3 h-11">
                  <Checkbox 
                    id="face" 
                    checked={faceEnhance}
                    onCheckedChange={(checked) => setFaceEnhance(checked as boolean)}
                    className="border-border/50"
                  />
                  <Label htmlFor="face" className="cursor-pointer text-sm font-light text-foreground/80">
                    Face Enhancement
                  </Label>
                </div>
              </div>
            </div>
          </Card>
        </div>

        {/* Upload Zone */}
        <div className="mb-10 animate-slide-up">
          <div
            className={`upload-zone ${isDragging ? "upload-zone-hover" : ""} cursor-pointer p-16 md:p-20 text-center`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <ImagePlus 
              className={`w-14 h-14 md:w-16 md:h-16 mx-auto mb-6 transition-all duration-300 ${
                isDragging ? "text-foreground scale-110" : "text-foreground/40"
              }`} 
              strokeWidth={1}
            />
            <h3 className="text-xl md:text-2xl font-light mb-3 text-foreground tracking-tight">
              {selectedFiles.length > 0 
                ? `${selectedFiles.length} ${selectedFiles.length === 1 ? 'file' : 'files'} selected`
                : "Drop images or click to browse"
              }
            </h3>
            <p className="text-sm text-muted-foreground font-light">
              JPG, PNG, WebP • Multiple files supported
            </p>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept="image/*"
              onChange={handleFileSelect}
              className="hidden"
            />
          </div>

          <div className="mt-8 flex justify-center">
            <Button
              size="lg"
              onClick={handleUpscale}
              disabled={selectedFiles.length === 0 || isProcessing}
              className="bg-primary hover:bg-primary/90 text-primary-foreground px-10 py-6 text-base font-light tracking-wide transition-all duration-300 elegant-shadow hover:shadow-xl disabled:opacity-50"
            >
              {isProcessing ? (
                <>
                  <div className="w-4 h-4 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin mr-3" />
                  Processing
                </>
              ) : (
                <>
                  <Upload className="w-4 h-4 mr-3" strokeWidth={1.5} />
                  Begin Upscale
                </>
              )}
            </Button>
          </div>
        </div>

        {/* Results Grid */}
        {failures.length > 0 && (
          <div className="mb-8 animate-fade-in">
            <h2 className="text-lg font-light mb-3 text-destructive tracking-tight">
              {failures.length === 1 ? "1 kép nem sikerült" : `${failures.length} kép nem sikerült`}
            </h2>
            <ul className="rounded-lg border border-destructive/30 bg-destructive/5 divide-y divide-destructive/15">
              {failures.map((f, idx) => (
                <li key={idx} className="px-4 py-3">
                  <p className="text-sm font-medium text-foreground truncate">{f.source}</p>
                  <p className="text-xs text-muted-foreground mt-0.5 break-words">{f.error}</p>
                </li>
              ))}
            </ul>
            <p className="text-xs text-muted-foreground mt-2 font-light">
              A részletes kimenet az upscale.log fájlban van.
            </p>
          </div>
        )}

        {results.length > 0 && (
          <div className="animate-fade-in">
            <h2 className="text-2xl font-light mb-8 text-foreground tracking-tight">
              Enhanced Images
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
              {results.map((result, idx) => (
                <Card 
                  key={idx} 
                  className="overflow-hidden elegant-border elegant-shadow hover:shadow-xl transition-all duration-500 group bg-card/50 backdrop-blur-sm"
                >
                  <div className="relative aspect-square overflow-hidden bg-muted/30">
                    <a
                      href={result.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      title="Open in new tab"
                    >
                      <img
                        src={result.url}
                        alt={result.filename}
                        className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
                      />
                    </a>
                  </div>
                  <div className="p-4 flex items-center justify-between border-t border-border/30">
                    <p className="text-xs text-muted-foreground font-light truncate flex-1 tracking-wide">
                      {result.filename}
                    </p>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="hover:bg-foreground hover:text-background transition-all duration-300 -mr-2"
                      asChild
                    >
                      <a href={result.url} download={result.filename}>
                        <Download className="w-4 h-4" strokeWidth={1.5} />
                      </a>
                    </Button>
                  </div>
                </Card>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Index;
