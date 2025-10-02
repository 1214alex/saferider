import { Map, Camera } from "lucide-react";
import { Button } from "./ui/button";

interface NavigationSidebarProps {
  activeView: "map" | "cctv";
  onViewChange: (view: "map" | "cctv") => void;
}

export function NavigationSidebar({ activeView, onViewChange }: NavigationSidebarProps) {
  return (
    <div className="w-16 bg-gray-900 flex flex-col items-center py-4 space-y-4">
      <div className="text-white text-xs mb-4">
        <div className="w-8 h-8 bg-red-600 rounded-full flex items-center justify-center">
          <span className="text-xs">MP</span>
        </div>
      </div>
      
      <Button
        variant={activeView === "map" ? "secondary" : "ghost"}
        size="sm"
        className={`w-12 h-12 p-0 ${
          activeView === "map" 
            ? "bg-white text-gray-900 hover:bg-gray-100" 
            : "text-gray-400 hover:text-white hover:bg-gray-800"
        }`}
        onClick={() => onViewChange("map")}
      >
        <Map className="w-5 h-5" />
      </Button>
      
      <Button
        variant={activeView === "cctv" ? "secondary" : "ghost"}
        size="sm"
        className={`w-12 h-12 p-0 ${
          activeView === "cctv" 
            ? "bg-white text-gray-900 hover:bg-gray-100" 
            : "text-gray-400 hover:text-white hover:bg-gray-800"
        }`}
        onClick={() => onViewChange("cctv")}
      >
        <Camera className="w-5 h-5" />
      </Button>
    </div>
  );
}