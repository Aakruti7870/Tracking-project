import { useState } from "react";
import { UserRole, Order, Plant, MixerTelemetry, ProofOfDelivery, ConcreteGrade } from "./types";
import { INITIAL_PLANTS, INITIAL_ORDERS, INITIAL_TELEMETRY } from "./mockData";
import { Navbar } from "./components/Navbar";
import { CustomerView } from "./components/CustomerView";
import { DriverView } from "./components/DriverView";
import { PlantOperationsView } from "./components/PlantOperationsView";
import { DispatcherFleetView } from "./components/DispatcherFleetView";
import { CentralAdminView } from "./components/CentralAdminView";
import { OrderModal } from "./components/OrderModal";
import { ChallanModal } from "./components/ChallanModal";
import { ProofOfDeliveryModal } from "./components/ProofOfDeliveryModal";

export function App() {
  const [currentRole, setCurrentRole] = useState<UserRole>("customer");
  const [orders, setOrders] = useState<Order[]>(INITIAL_ORDERS);
  const [plants, setPlants] = useState<Plant[]>(INITIAL_PLANTS);
  const [telemetry, setTelemetry] = useState<Record<string, MixerTelemetry>>(INITIAL_TELEMETRY);

  // Modals
  const [orderModalOpen, setOrderModalOpen] = useState(false);
  const [orderModalData, setOrderModalData] = useState<{ grade?: ConcreteGrade; quantity?: number; notes?: string }>({});
  const [challanOrder, setChallanOrder] = useState<Order | null>(null);
  const [podOrder, setPodOrder] = useState<Order | null>(null);

  // Create new order
  const handleCreateOrder = (orderData: {
    plant_id: string;
    grade: ConcreteGrade;
    quantity_m3: number;
    site_name: string;
    site_address: string;
    delivery_date: string;
    delivery_time: string;
    pump_type: Order["pump_type"];
    slump: string;
    rate_per_m3: number;
    total_amount: number;
  }) => {
    const plant = plants.find((p) => p.id === orderData.plant_id) || plants[0];
    const newId = `ord-${Date.now()}`;
    const orderNum = `RMC-2026-${Math.floor(1000 + Math.random() * 9000)}`;
    const challanNum = `CHL-${plant.city.substring(0, 3).toUpperCase()}-${Math.floor(1000 + Math.random() * 9000)}-A`;

    const newOrder: Order = {
      id: newId,
      order_number: orderNum,
      customer_name: "Aakruti Infra Projects Ltd.",
      customer_phone: "+91 98202 81720",
      plant_id: plant.id,
      plant_name: plant.name,
      grade: orderData.grade,
      quantity_m3: orderData.quantity_m3,
      site_name: orderData.site_name,
      site_address: orderData.site_address,
      delivery_date: orderData.delivery_date,
      delivery_time: orderData.delivery_time,
      status: "CONFIRMED",
      payment_status: "PAID",
      pump_type: orderData.pump_type,
      slump: orderData.slump,
      tm_number: "MH-04-EK-9214",
      driver_name: "Rameshwar Gurjar",
      driver_mobile: "+91 98451 22340",
      challan_number: challanNum,
      rate_per_m3: orderData.rate_per_m3,
      total_amount: orderData.total_amount,
      created_at: new Date().toISOString(),
    };

    setOrders((prev) => [newOrder, ...prev]);

    // Add telemetry record for the order
    setTelemetry((prev) => ({
      ...prev,
      [newId]: {
        order_id: newId,
        tm_number: "MH-04-EK-9214",
        driver_name: "Rameshwar Gurjar",
        driver_mobile: "+91 98451 22340",
        capacity_m3: 7,
        current_load_m3: Math.min(7, orderData.quantity_m3),
        speed_kmh: 0,
        drum_rpm: 3.2,
        drum_direction: "AGITATING",
        concrete_temp_c: 27.2,
        slump_measured_mm: 120,
        progress_percent: 0,
        eta_minutes: 25,
        current_lat: plant.lat,
        current_lng: plant.lng,
        start_lat: plant.lat,
        start_lng: plant.lng,
        dest_lat: 19.232,
        dest_lng: 72.985,
        status: "EN_ROUTE_SITE",
      },
    }));
  };

  // Update order status
  const handleUpdateOrderStatus = (orderId: string, newStatus: Order["status"]) => {
    setOrders((prev) =>
      prev.map((o) => (o.id === orderId ? { ...o, status: newStatus } : o))
    );

    // Update telemetry progress
    setTelemetry((prev) => {
      const current = prev[orderId];
      if (!current) return prev;
      let progress = current.progress_percent;
      let speed = current.speed_kmh;
      if (newStatus === "DISPATCHED") {
        progress = 50;
        speed = 40;
      } else if (newStatus === "ON_SITE" || newStatus === "POURING") {
        progress = 100;
        speed = 0;
      } else if (newStatus === "DELIVERED") {
        progress = 100;
        speed = 0;
      }
      return {
        ...prev,
        [orderId]: {
          ...current,
          progress_percent: progress,
          speed_kmh: speed,
        },
      };
    });
  };

  // Submit Proof of Delivery (POD)
  const handleSubmitPOD = (orderId: string, pod: ProofOfDelivery) => {
    setOrders((prev) =>
      prev.map((o) =>
        o.id === orderId
          ? {
              ...o,
              status: "DELIVERED",
              pod,
            }
          : o
      )
    );
  };

  // Transfer calculation to order modal
  const handleApplyCalculation = (calc: { grade: ConcreteGrade; quantity: number; notes: string }) => {
    setOrderModalData({
      grade: calc.grade,
      quantity: calc.quantity,
      notes: calc.notes,
    });
    setOrderModalOpen(true);
  };

  return (
    <div className="min-h-screen bg-[#0E1116] text-[#F7F8F9] flex flex-col selection:bg-[#FF6A00]/30 selection:text-[#FF7A18]">
      {/* Top Navbar with role switcher */}
      <Navbar
        currentRole={currentRole}
        onSelectRole={setCurrentRole}
        onOpenNewOrder={() => {
          setOrderModalData({});
          setOrderModalOpen(true);
        }}
        orderCount={orders.length}
      />

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {currentRole === "customer" && (
          <CustomerView
            orders={orders}
            plants={plants}
            telemetry={telemetry}
            onOpenNewOrder={() => {
              setOrderModalData({});
              setOrderModalOpen(true);
            }}
            onApplyCalculation={handleApplyCalculation}
            onUpdateOrderStatus={handleUpdateOrderStatus}
            onOpenChallan={(order) => setChallanOrder(order)}
            onOpenPod={(order) => setPodOrder(order)}
          />
        )}

        {currentRole === "driver" && (
          <DriverView
            orders={orders}
            telemetry={telemetry}
            onUpdateStatus={handleUpdateOrderStatus}
            onOpenChallan={(order) => setChallanOrder(order)}
            onOpenPod={(order) => setPodOrder(order)}
          />
        )}

        {currentRole === "plant_owner" && (
          <PlantOperationsView
            plants={plants}
            orders={orders}
            onUpdateStatus={handleUpdateOrderStatus}
            onOpenChallan={(order) => setChallanOrder(order)}
          />
        )}

        {currentRole === "dispatcher" && (
          <DispatcherFleetView
            orders={orders}
            telemetry={telemetry}
            onUpdateStatus={handleUpdateOrderStatus}
            onOpenChallan={(order) => setChallanOrder(order)}
          />
        )}

        {currentRole === "central_admin" && (
          <CentralAdminView orders={orders} plants={plants} />
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-[#1F2937] bg-[#0B0E13] py-5 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-gray-500">
          <div className="flex items-center gap-2">
            <span className="font-bold text-gray-400">TrackMyRMC</span>
            <span>·</span>
            <span>Ready Mix Concrete Supply Chain & Telematics</span>
          </div>
          <div className="flex items-center gap-4 text-[11px]">
            <span>IS 456 : 2000 & IS 4926 : 2003 Compliant</span>
            <span>·</span>
            <span className="text-[#38A169]">CAN-Bus & GPS Stream Active</span>
          </div>
        </div>
      </footer>

      {/* Order Booking Modal */}
      <OrderModal
        isOpen={orderModalOpen}
        onClose={() => setOrderModalOpen(false)}
        plants={plants}
        initialData={orderModalData}
        onSubmit={handleCreateOrder}
      />

      {/* Digital Delivery Challan Modal */}
      <ChallanModal order={challanOrder} onClose={() => setChallanOrder(null)} />

      {/* Proof of Delivery (POD) Modal */}
      <ProofOfDeliveryModal
        order={podOrder}
        isOpen={!!podOrder}
        onClose={() => setPodOrder(null)}
        onSubmitPOD={handleSubmitPOD}
      />
    </div>
  );
}

export default App;
