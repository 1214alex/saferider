import { useEffect,useState } from "react";
import { MapView } from "./components/MapView";
import { PeopleSidebar } from "./components/PeopleSidebar";
import { NearbyVehicles } from "./components/NearbyVehicles";
import { NavigationSidebar } from "./components/NavigationSidebar";
import { CCTVPage } from "./components/CCTVPage";

interface Person {
  id: string;
  name: string;
  status: "missing" | "found" | "searching";
  lat: number; // 위도(도)
  lng: number; // 경도(도)
  phone?: string;
  email?: string;
  lastSeen?: string;
  age?: number;
  description?: string;
  reportedBy?: string;
  caseNumber?: string;
}

interface Vehicle {
  id: string;
  type: "police" | "taxi" | "delivery";
  vehicleModel: string;
  licensePlate: string;
  driver: string;
  distance: number;
  eta: string;
  status: "available" | "responding" | "busy";
  unit?: string;
}

interface CCTVCamera {
  id: string;
  name: string;
  location: string;
  status: "online" | "offline" | "recording";
  lat: number; // 위도(도)
  lng: number; // 경도(도)
  lastDetection?: string;
  detectionType?: "person" | "vehicle" | "motion";
  isActive: boolean;
}

const API_BASE = import.meta.env.VITE_API_BASE as string;

const mockVehicles: Vehicle[] = [
  { id: "v1", type: "police",  vehicleModel: "Ford Explorer Police", licensePlate: "POL-123", driver: "Officer Johnson", distance: 150, eta: "3 min", status: "available",  unit: "Unit 15" },
  { id: "v2", type: "police",  vehicleModel: "Chevrolet Tahoe Police", licensePlate: "POL-456", driver: "Officer Smith",   distance: 300, eta: "7 min", status: "responding", unit: "Unit 22" },
  { id: "v3", type: "taxi",    vehicleModel: "Toyota Camry",          licensePlate: "TAX-789", driver: "Mike Rodriguez",   distance: 200, eta: "5 min", status: "available" },
  { id: "v4", type: "delivery",vehicleModel: "Honda Civic",           licensePlate: "DEL-012", driver: "Sarah Kim",        distance: 75,  eta: "2 min", status: "available" },
  { id: "v5", type: "taxi",    vehicleModel: "Nissan Altima",         licensePlate: "TAX-345", driver: "David Wilson",     distance: 400, eta: "8 min", status: "busy" },
  { id: "v6", type: "delivery",vehicleModel: "Ford Transit",          licensePlate: "DEL-678", driver: "Jenny Martinez",   distance: 250, eta: "6 min", status: "available" }
];

// ✅ CCTV도 실제 좌표 사용
const mockCCTVCameras: CCTVCamera[] = [
  { id: "cam1", name: "Downtown Plaza Cam 1", location: "Seoul Plaza",  status: "recording", lat: 37.5663, lng: 126.9779, lastDetection: "2 min ago",  detectionType: "person",  isActive: true },
  { id: "cam2", name: "Shopping Mall Entrance", location: "Suwon Mall", status: "online",    lat: 37.2596, lng: 127.0329, lastDetection: "15 min ago", detectionType: "vehicle", isActive: true },
  { id: "cam3", name: "Park Central Camera",    location: "Daejeon",    status: "online",    lat: 36.3510, lng: 127.3850, isActive: false },
  { id: "cam4", name: "Train Station Cam 3",    location: "Daegu",      status: "recording", lat: 35.8810, lng: 128.6280, lastDetection: "5 min ago",  detectionType: "person",  isActive: true },
  { id: "cam5", name: "University Campus Cam",  location: "Busan Univ", status: "online",    lat: 35.2327, lng: 129.0795, lastDetection: "30 min ago", detectionType: "motion",  isActive: true },
  { id: "cam6", name: "Highway Overpass",       location: "Gyeryong",   status: "offline",   lat: 36.2740, lng: 127.2480, isActive: false },
  { id: "cam7", name: "Residential Area Cam",   location: "Ulsan",      status: "recording", lat: 35.5384, lng: 129.3114, lastDetection: "1 hour ago", detectionType: "vehicle", isActive: true }
];

export default function App() {
  const [people, setPeople] = useState<Person[]>([]);
  const [selectedPerson, setSelectedPerson] = useState<Person | null>(null);

  const [activeView, setActiveView] = useState<"map" | "cctv">("map");
  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${API_BASE}/api/missing`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ date: "20250901", rowSize: 30, page: 1 })
        });
        const arr: Person[] = await r.json();
        setPeople(arr);
        setSelectedPerson(arr[0] ?? null);
      } catch (e) {
        console.error(e);
        // 실패 시 로컬 목 사용 원하면 여기서 setPeople(mockPeople)
      }
    })();
  }, []);

  const handlePersonSelect = (person: Person) => setSelectedPerson(person);
  const handleViewChange = (view: "map" | "cctv") => setActiveView(view);

  return (
    <div className="h-screen flex bg-background">
      <NavigationSidebar activeView={activeView} onViewChange={handleViewChange} />

      <div className="flex-1 flex flex-col">
        {activeView === "map" ? (
          <>
            <div className="flex flex-1 gap-4 p-4">
              {/* ✅ 지도 컨테이너에 최소 높이 보장 */}
              <div className="flex-1 min-h-[560px]">
                <MapView
                  people={people}
                  selectedPerson={selectedPerson}
                  onPersonSelect={handlePersonSelect}
                />
              </div>

              <div className="w-80 flex flex-col">
                <PeopleSidebar
                  people={people}
                  selectedPerson={selectedPerson}
                  onPersonSelect={handlePersonSelect}
                />
              </div>
            </div>

            <div className="h-64 border-t p-4">
              <NearbyVehicles
                vehicles={mockVehicles}
                selectedPersonName={selectedPerson?.name}
              />
            </div>
          </>
        ) : (
          <div className="flex-1 p-4">
            <CCTVPage cameras={mockCCTVCameras} />
          </div>
        )}
      </div>
    </div>
  );
}
