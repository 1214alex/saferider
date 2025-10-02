import { Car, Navigation, Clock, Fuel, Shield, Truck, Filter } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { useState } from "react";

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

interface NearbyVehiclesProps {
  vehicles: Vehicle[];
  selectedPersonName?: string;
}

function getVehicleIcon(type: string) {
  switch (type) {
    case 'police': return Shield;
    case 'taxi': return Car;
    case 'delivery': return Truck;
    default: return Car;
  }
}

function getVehicleColor(type: string) {
  switch (type) {
    case 'police': return 'bg-blue-100 text-blue-600';
    case 'taxi': return 'bg-yellow-100 text-yellow-600';
    case 'delivery': return 'bg-green-100 text-green-600';
    default: return 'bg-gray-100 text-gray-600';
  }
}

export function NearbyVehicles({ vehicles, selectedPersonName }: NearbyVehiclesProps) {
  const [statusFilter, setStatusFilter] = useState<"all" | "available" | "busy" | "responding">("all");
  
  const filteredVehicles = vehicles.filter(vehicle => {
    if (statusFilter === "all") return true;
    return vehicle.status === statusFilter;
  });
  
  const policeCount = vehicles.filter(v => v.type === 'police').length;
  const taxiCount = vehicles.filter(v => v.type === 'taxi').length;
  const deliveryCount = vehicles.filter(v => v.type === 'delivery').length;
  
  const availableCount = vehicles.filter(v => v.status === 'available').length;
  const busyCount = vehicles.filter(v => v.status === 'busy').length;
  const respondingCount = vehicles.filter(v => v.status === 'responding').length;
  
  return (
    <div className="h-full">
      <Card className="h-full">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2">
            <Shield className="w-5 h-5" />
            Emergency Response Vehicles
            {selectedPersonName && (
              <span className="text-sm text-muted-foreground">
                near {selectedPersonName}'s location
              </span>
            )}
          </CardTitle>
          <div className="flex gap-4 text-sm text-muted-foreground">
            <span>{policeCount} police</span>
            <span>{taxiCount} taxis</span>
            <span>{deliveryCount} delivery</span>
          </div>
          
          {/* Status Filter */}
          <div className="flex gap-2 mt-3">
            <div className="flex items-center gap-1 text-xs text-muted-foreground mr-2">
              <Filter className="w-3 h-3" />
              Filter:
            </div>
            <Button
              size="sm"
              variant={statusFilter === "all" ? "default" : "outline"}
              className="text-xs px-2 py-1 h-6"
              onClick={() => setStatusFilter("all")}
            >
              All ({vehicles.length})
            </Button>
            <Button
              size="sm"
              variant={statusFilter === "available" ? "default" : "outline"}
              className="text-xs px-2 py-1 h-6"
              onClick={() => setStatusFilter("available")}
            >
              Available ({availableCount})
            </Button>
            <Button
              size="sm"
              variant={statusFilter === "busy" ? "default" : "outline"}
              className="text-xs px-2 py-1 h-6"
              onClick={() => setStatusFilter("busy")}
            >
              Busy ({busyCount})
            </Button>
            <Button
              size="sm"
              variant={statusFilter === "responding" ? "default" : "outline"}
              className="text-xs px-2 py-1 h-6"
              onClick={() => setStatusFilter("responding")}
            >
              Responding ({respondingCount})
            </Button>
          </div>
        </CardHeader>
        
        <CardContent className="space-y-3">
          {filteredVehicles.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <Car className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">No vehicles match the current filter</p>
            </div>
          ) : (
            filteredVehicles.map((vehicle) => {
            const IconComponent = getVehicleIcon(vehicle.type);
            const colorClass = getVehicleColor(vehicle.type);
            
            return (
              <div
                key={vehicle.id}
                className="flex items-center justify-between p-3 border rounded-lg hover:bg-muted/30 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-lg ${colorClass}`}>
                    <IconComponent className="w-4 h-4" />
                  </div>
                  
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm capitalize">{vehicle.type}</span>
                      {vehicle.unit && (
                        <span className="text-xs text-muted-foreground">#{vehicle.unit}</span>
                      )}
                      <Badge 
                        variant="outline"
                        className={`text-xs ${
                          vehicle.status === 'available' 
                            ? 'border-green-500 text-green-700 bg-green-50' 
                            : vehicle.status === 'responding'
                            ? 'border-blue-500 text-blue-700 bg-blue-50'
                            : 'border-yellow-500 text-yellow-700 bg-yellow-50'
                        }`}
                      >
                        {vehicle.status}
                      </Badge>
                    </div>
                    
                    <div className="text-xs text-muted-foreground">
                      <div>{vehicle.vehicleModel}</div>
                      <div>Driver: {vehicle.driver}</div>
                      <div>Plate: {vehicle.licensePlate}</div>
                    </div>
                  </div>
                </div>
                
                <div className="text-right">
                  <div className="flex items-center gap-1 text-sm mb-1">
                    <Navigation className="w-3 h-3" />
                    <span>{vehicle.distance}m away</span>
                  </div>
                  
                  <div className="flex items-center gap-1 text-xs text-muted-foreground mb-2">
                    <Clock className="w-3 h-3" />
                    <span>ETA: {vehicle.eta}</span>
                  </div>
                  
                  <Button 
                    size="sm" 
                    variant={vehicle.type === 'police' ? 'destructive' : 'outline'}
                    className="text-xs px-2 py-1"
                  >
                    {vehicle.type === 'police' ? 'Dispatch' : 'Request'}
                  </Button>
                </div>
              </div>
            );
            })
          )}
          
          <div className="pt-2 border-t flex gap-2">
            <Button className="flex-1" size="sm" variant="destructive">
              <Shield className="w-3 h-3 mr-1" />
              Emergency Alert
            </Button>
            <Button className="flex-1" size="sm" variant="outline">
              <Navigation className="w-3 h-3 mr-1" />
              Coordinate Search
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}