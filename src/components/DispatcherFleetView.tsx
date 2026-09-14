import { useState } from "react";
import { Order, MixerTelemetry } from "../types";
import { Truck, Radio, RotateCw, MapPin, Gauge, Phone, CheckCircle, Clock } from "lucide-react";

interface DispatcherFleetViewProps {
  orders: Order[];
  telemetry: Record<string, MixerTelemetry>;
  onUpdateStatus: (orderId: string, status: Order["status"]) => void;
  onOpenChallan: (order: Order) => void;
}

export function DispatcherFleetView({
  orders,
  telemetry,
  onUpdateStatus,
  onOpenChallan,
}: DispatcherFleetViewProps) {
  const fleet = [
    {
      id: "tm-1",
      plate: "MH-04-EK-9214",
      capacity: "7 m³",
      driver: "Rameshwar Gurjar",
      phone: "+91 98451 22340",
      status: "IN_TRANSIT",
      destination: "Lodha Amara Tower C",
      speed: 38,
      rpm: 3.2,
      temp: 27.4,
      order_id: "ord-101",
    },
    {
      id: "tm-2",
      plate: "MH-04-EK-8109",
      capacity: "7 m³",
      driver: "Santosh Kadam",
      phone: "+91 97654 88120",
      status: "LOADING_SILO",
      destination: "Metro Line 4 - Pier #218",
      speed: 0,
      rpm: 12.0,
      temp: 26.8,
      order_id: "ord-102",
    },
    {
      id: "tm-3",
      plate: "MH-03-CB-4491",
      capacity: "6 m³",
      driver: "Vikram Patil",
      phone: "+91 98230 45671",
      status: "RETURNING_EMPTY",
      destination: "UltraTech Plant Thane",
      speed: 42,
      rpm: 1.0,
      temp: 28.1,
      order_id: "ord-103",
    },
    {
      id: "tm-4",
      plate: "MH-04-AB-5510",
      capacity: "8 m³",
      driver: "Deepak Sharma",
      phone: "+91 98211 44556",
      status: "STANDBY_YARD",
      destination: "Plant Parking Bay #3",
      speed: 0,
      rpm: 0,
      temp: 25.0,
      order_id: undefined,
    },
  ];

  return (
    <div className="space-y-6">
      {/* Fleet Overview Header */}
      <div className="p-4 rounded-2xl bg-[#14181F] border border-[#2D3748] flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-xl bg-[#FF6A00]/10 text-[#FF7A18]">
            <Radio className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white">Central Transit Mixer Telematics & Fleet Dispatch</h2>
            <p className="text-xs text-gray-400">Live CAN-Bus telematics via IoT gateway</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-[#12251A] text-[#38A169] border border-[#38A169]/30">
            4 Mixers Active · 1 Standby
          </span>
        </div>
      </div>

      {/* Fleet Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {fleet.map((tm) => {
          return (
            <div
              key={tm.id}
              className="p-5 rounded-2xl bg-[#14181F] border border-[#2D3748] space-y-4 shadow-xl"
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-base font-extrabold text-white">{tm.plate}</span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-[#1D232D] text-gray-300">
                      {tm.capacity}
                    </span>
                  </div>
                  <p className="text-xs text-gray-400 mt-0.5">Pilot: {tm.driver} ({tm.phone})</p>
                </div>

                <span
                  className={`px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                    tm.status === "IN_TRANSIT"
                      ? "bg-[#FF6A00]/20 text-[#FF7A18] border border-[#FF6A00]/30 animate-pulse"
                      : tm.status === "LOADING_SILO"
                      ? "bg-[#3B82F6]/20 text-[#3B82F6] border border-blue-500/30"
                      : tm.status === "RETURNING_EMPTY"
                      ? "bg-[#38A169]/20 text-[#38A169] border border-[#38A169]/30"
                      : "bg-[#1D232D] text-gray-400"
                  }`}
                >
                  {tm.status.replace("_", " ")}
                </span>
              </div>

              {/* Destination */}
              <div className="p-3 rounded-xl bg-[#1D232D] border border-[#2D3748] flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <MapPin className="w-4 h-4 text-[#FF7A18]" />
                  <div>
                    <span className="text-[10px] text-gray-400 uppercase font-semibold">Active Destination</span>
                    <p className="font-bold text-white">{tm.destination}</p>
                  </div>
                </div>
              </div>

              {/* Telemetry stats */}
              <div className="grid grid-cols-3 gap-2 text-center text-xs">
                <div className="p-2.5 rounded-xl bg-[#1D232D] border border-[#2D3748]">
                  <span className="text-[10px] text-gray-400">Road Speed</span>
                  <p className="text-sm font-bold text-white font-mono mt-0.5">{tm.speed} km/h</p>
                </div>
                <div className="p-2.5 rounded-xl bg-[#1D232D] border border-[#2D3748]">
                  <span className="text-[10px] text-gray-400">Drum Rotation</span>
                  <p className="text-sm font-bold text-[#FF7A18] font-mono mt-0.5">{tm.rpm} RPM</p>
                </div>
                <div className="p-2.5 rounded-xl bg-[#1D232D] border border-[#2D3748]">
                  <span className="text-[10px] text-gray-400">Mix Temp</span>
                  <p className="text-sm font-bold text-white font-mono mt-0.5">{tm.temp} °C</p>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
