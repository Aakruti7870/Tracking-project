import { useState, useRef, useEffect } from "react";
import { Order, ProofOfDelivery } from "../types";
import { X, CheckCircle2, PenTool, ShieldCheck, Camera, Eraser } from "lucide-react";

interface ProofOfDeliveryModalProps {
  order: Order | null;
  isOpen: boolean;
  onClose: () => void;
  onSubmitPOD: (orderId: string, pod: ProofOfDelivery) => void;
}

export function ProofOfDeliveryModal({ order, isOpen, onClose, onSubmitPOD }: ProofOfDeliveryModalProps) {
  const [receiverName, setReceiverName] = useState("Er. Rajesh Deshmukh");
  const [receiverPhone, setReceiverPhone] = useState("+91 98199 44321");
  const [designation, setDesignation] = useState("Site Quality Engineer");
  const [deliveredQuantity, setDeliveredQuantity] = useState(order?.quantity_m3 || 24);
  const [slumpAtPour, setSlumpAtPour] = useState(115);
  const [cubesTaken, setCubesTaken] = useState(true);
  const [cubeCount, setCubeCount] = useState(6);
  const [notes, setNotes] = useState("Slump verified at chute. Concrete placed continuously without segregation.");
  const [hasSignature, setHasSignature] = useState(false);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const isDrawing = useRef(false);

  useEffect(() => {
    if (order?.pod) {
      setReceiverName(order.pod.receiver_name);
      setReceiverPhone(order.pod.receiver_phone);
      setDesignation(order.pod.receiver_designation);
      setDeliveredQuantity(order.pod.delivered_quantity_m3);
      setSlumpAtPour(order.pod.slump_at_pour_mm);
      setCubesTaken(order.pod.cube_samples_taken);
      setCubeCount(order.pod.cube_count);
      setNotes(order.pod.site_notes);
      setHasSignature(true);
    } else if (order) {
      setDeliveredQuantity(order.quantity_m3);
    }
  }, [order]);

  if (!isOpen || !order) return null;

  // Canvas drawing handlers
  const startDrawing = (e: React.MouseEvent<HTMLCanvasElement> | React.TouchEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    
    isDrawing.current = true;
    const rect = canvas.getBoundingClientRect();
    const x = "touches" in e ? e.touches[0].clientX - rect.left : e.clientX - rect.left;
    const y = "touches" in e ? e.touches[0].clientY - rect.top : e.clientY - rect.top;
    
    ctx.strokeStyle = "#14181F";
    ctx.lineWidth = 2.5;
    ctx.lineCap = "round";
    ctx.beginPath();
    ctx.moveTo(x, y);
    setHasSignature(true);
  };

  const draw = (e: React.MouseEvent<HTMLCanvasElement> | React.TouchEvent<HTMLCanvasElement>) => {
    if (!isDrawing.current) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const rect = canvas.getBoundingClientRect();
    const x = "touches" in e ? e.touches[0].clientX - rect.left : e.clientX - rect.left;
    const y = "touches" in e ? e.touches[0].clientY - rect.top : e.clientY - rect.top;

    ctx.lineTo(x, y);
    ctx.stroke();
  };

  const stopDrawing = () => {
    isDrawing.current = false;
  };

  const clearCanvas = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    setHasSignature(false);
  };

  const applyDefaultSignature = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    clearCanvas();
    ctx.strokeStyle = "#0E1116";
    ctx.lineWidth = 2.5;
    ctx.font = "italic 24px 'Caveat', cursive, serif";
    ctx.strokeText(receiverName || "R. Deshmukh", 40, 50);
    setHasSignature(true);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const podData: ProofOfDelivery = {
      order_id: order.id,
      receiver_name: receiverName,
      receiver_phone: receiverPhone,
      receiver_designation: designation,
      delivered_quantity_m3: deliveredQuantity,
      delivered_at: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      slump_at_pour_mm: slumpAtPour,
      cube_samples_taken: cubesTaken,
      cube_count: cubeCount,
      site_notes: notes,
      verified_by_driver: true,
    };
    onSubmitPOD(order.id, podData);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm overflow-y-auto">
      <div className="relative w-full max-w-xl bg-[#14181F] border border-[#2D3748] rounded-2xl shadow-2xl overflow-hidden my-8">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#2D3748] bg-[#1D232D]">
          <div>
            <span className="text-[10px] font-bold tracking-widest text-[#38A169] uppercase flex items-center gap-1">
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>IS 4926 Quality Receipt</span>
            </span>
            <h3 className="text-base font-bold text-white">Digital Proof of Delivery (POD)</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {/* Order Snapshot Banner */}
          <div className="p-3 rounded-xl bg-[#1D232D] border border-[#2D3748] flex items-center justify-between text-xs">
            <div>
              <span className="text-[10px] text-gray-400 uppercase">Order Ref</span>
              <p className="font-bold text-white font-mono">{order.order_number}</p>
              <p className="text-[11px] text-gray-400 truncate max-w-[240px]">{order.site_name}</p>
            </div>
            <div className="text-right">
              <span className="text-[10px] text-gray-400 uppercase">Mix Design</span>
              <p className="font-bold text-[#FF7A18] font-mono">{order.grade}</p>
              <p className="text-[11px] text-gray-300 font-bold">{order.quantity_m3} m³</p>
            </div>
          </div>

          {/* Receiver Information */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-gray-300 mb-1">Receiver Full Name</label>
              <input
                type="text"
                value={receiverName}
                onChange={(e) => setReceiverName(e.target.value)}
                className="w-full bg-[#1D232D] border border-[#2D3748] rounded-xl px-3 py-2 text-xs text-white focus:border-[#38A169] focus:outline-none"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-300 mb-1">Designation / Role</label>
              <input
                type="text"
                value={designation}
                onChange={(e) => setDesignation(e.target.value)}
                className="w-full bg-[#1D232D] border border-[#2D3748] rounded-xl px-3 py-2 text-xs text-white focus:border-[#38A169] focus:outline-none"
                placeholder="e.g. Project Engineer"
                required
              />
            </div>
          </div>

          {/* Slump & Cube Tests */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-gray-300 mb-1">Measured Site Slump (mm)</label>
              <input
                type="number"
                min="50"
                max="200"
                value={slumpAtPour}
                onChange={(e) => setSlumpAtPour(parseInt(e.target.value) || 115)}
                className="w-full bg-[#1D232D] border border-[#2D3748] rounded-xl px-3 py-2 text-xs text-white font-mono font-bold focus:border-[#38A169] focus:outline-none"
                required
              />
              <p className="text-[10px] text-gray-500 mt-1">Acceptable tolerance: 100 - 140 mm</p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-300 mb-1">Delivered Volume (m³)</label>
              <input
                type="number"
                step="0.5"
                value={deliveredQuantity}
                onChange={(e) => setDeliveredQuantity(parseFloat(e.target.value) || order.quantity_m3)}
                className="w-full bg-[#1D232D] border border-[#2D3748] rounded-xl px-3 py-2 text-xs text-white font-mono font-bold focus:border-[#38A169] focus:outline-none"
                required
              />
            </div>
          </div>

          {/* Cube test toggle */}
          <div className="p-3 rounded-xl bg-[#1D232D] border border-[#2D3748] flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <input
                type="checkbox"
                id="cube-toggle"
                checked={cubesTaken}
                onChange={(e) => setCubesTaken(e.target.checked)}
                className="w-4 h-4 accent-[#38A169] rounded cursor-pointer"
              />
              <label htmlFor="cube-toggle" className="text-xs text-gray-300 font-medium cursor-pointer">
                Cast Compressive Strength Cubes (IS 516)
              </label>
            </div>
            {cubesTaken && (
              <span className="text-xs font-bold text-[#38A169] font-mono">
                {cubeCount} Cubes Cast (7d & 28d)
              </span>
            )}
          </div>

          {/* Site Signature Pad */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-semibold text-gray-300 flex items-center gap-1.5">
                <PenTool className="w-3.5 h-3.5 text-[#FF7A18]" />
                <span>Site Receiver Signature</span>
              </label>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={applyDefaultSignature}
                  className="text-[10px] text-[#38A169] hover:underline"
                >
                  Quick Sign
                </button>
                <button
                  type="button"
                  onClick={clearCanvas}
                  className="text-[10px] text-gray-400 hover:text-red-400 flex items-center gap-1"
                >
                  <Eraser className="w-3 h-3" />
                  <span>Clear</span>
                </button>
              </div>
            </div>

            <div className="bg-white rounded-xl border border-gray-400 overflow-hidden touch-none">
              <canvas
                ref={canvasRef}
                width={500}
                height={90}
                onMouseDown={startDrawing}
                onMouseMove={draw}
                onMouseUp={stopDrawing}
                onMouseLeave={stopDrawing}
                onTouchStart={startDrawing}
                onTouchMove={draw}
                onTouchEnd={stopDrawing}
                className="w-full h-[90px] cursor-crosshair bg-gray-50"
              />
            </div>
            <p className="text-[10px] text-gray-500 mt-1">Sign using mouse or touchscreen to finalize delivery acceptance</p>
          </div>

          {/* Notes */}
          <div>
            <label className="block text-xs font-semibold text-gray-300 mb-1">Site Quality Notes & Observations</label>
            <textarea
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full bg-[#1D232D] border border-[#2D3748] rounded-xl px-3 py-2 text-xs text-white focus:border-[#38A169] focus:outline-none"
            />
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-xs font-semibold text-gray-400 hover:text-white"
            >
              Cancel
            </button>
            <button
              id="confirm-pod-btn"
              type="submit"
              className="flex items-center gap-1.5 px-6 py-2.5 rounded-xl bg-[#38A169] hover:bg-[#276749] text-white font-bold text-xs shadow-lg shadow-[#38A169]/25 transition-all"
            >
              <CheckCircle2 className="w-4 h-4" />
              <span>Verify & Complete Delivery</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
