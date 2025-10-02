import { Camera, Eye, EyeOff, Play, Pause, Search, AlertTriangle, MapPin, Clock } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Avatar, AvatarFallback } from "./ui/avatar";
import { useState } from "react";

interface CCTVCamera {
  id: string;
  name: string;
  location: string;
  status: "online" | "offline" | "recording";
  lat: number;
  lng: number;
  lastDetection?: string;
  detectionType?: "person" | "vehicle" | "motion";
  isActive: boolean;
}

interface CCTVSidebarProps {
  cameras: CCTVCamera[];
  selectedPersonName?: string;
  onCameraSelect: (camera: CCTVCamera) => void;
}

export function CCTVSidebar({ cameras, selectedPersonName, onCameraSelect }: CCTVSidebarProps) {
  const [selectedCamera, setSelectedCamera] = useState<CCTVCamera | null>(null);
  const onlineCameras = cameras.filter(c => c.status === 'online').length;
  const recordingCameras = cameras.filter(c => c.status === 'recording').length;
  const recentDetections = cameras.filter(c => c.lastDetection).length;

  const handleCameraClick = (camera: CCTVCamera) => {
    setSelectedCamera(camera);
    onCameraSelect(camera);
  };

  return (
    <div className="h-full flex flex-col">
      <div className="p-4 border-b">
        <div className="flex items-center gap-2 mb-2">
          <Camera className="w-5 h-5 text-blue-600" />
          <h2 className="mb-0">CCTV Network</h2>
        </div>
        <div className="flex gap-4 text-sm text-muted-foreground">
          <span>{onlineCameras} online</span>
          <span>{recordingCameras} recording</span>
          <span>{recentDetections} alerts</span>
        </div>
        {selectedPersonName && (
          <div className="mt-2 p-2 bg-red-50 rounded border">
            <p className="text-xs text-red-700">
              <AlertTriangle className="w-3 h-3 inline mr-1" />
              Searching for {selectedPersonName}
            </p>
          </div>
        )}
      </div>

      <div className="flex-1 overflow-auto p-4 space-y-3">
        {cameras.map((camera) => (
          <Card 
            key={camera.id}
            className={`cursor-pointer transition-all duration-200 hover:shadow-md ${
              selectedCamera?.id === camera.id ? 'ring-2 ring-blue-500 bg-blue-50' : ''
            }`}
            onClick={() => handleCameraClick(camera)}
          >
            <CardContent className="p-4">
              <div className="flex items-start gap-3">
                <div className={`p-2 rounded-lg ${
                  camera.status === 'online' 
                    ? 'bg-green-100' 
                    : camera.status === 'recording'
                    ? 'bg-blue-100'
                    : 'bg-gray-100'
                }`}>
                  <Camera className={`w-4 h-4 ${
                    camera.status === 'online' 
                      ? 'text-green-600' 
                      : camera.status === 'recording'
                      ? 'text-blue-600'
                      : 'text-gray-600'
                  }`} />
                </div>
                
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h4 className="truncate text-sm">{camera.name}</h4>
                    <Badge 
                      variant="outline"
                      className={`text-xs ${
                        camera.status === 'online' 
                          ? 'border-green-500 text-green-700 bg-green-50' 
                          : camera.status === 'recording'
                          ? 'border-blue-500 text-blue-700 bg-blue-50'
                          : 'border-gray-500 text-gray-700 bg-gray-50'
                      }`}
                    >
                      {camera.status}
                    </Badge>
                  </div>
                  
                  <div className="text-xs text-muted-foreground mb-2">
                    <div className="flex items-center gap-1">
                      <MapPin className="w-3 h-3" />
                      <span>{camera.location}</span>
                    </div>
                  </div>

                  {camera.lastDetection && (
                    <div className="flex items-center gap-2">
                      <div className={`w-2 h-2 rounded-full ${
                        camera.detectionType === 'person' ? 'bg-red-500' :
                        camera.detectionType === 'vehicle' ? 'bg-yellow-500' : 'bg-blue-500'
                      }`} />
                      <span className="text-xs text-muted-foreground">
                        {camera.detectionType} detected {camera.lastDetection}
                      </span>
                    </div>
                  )}
                </div>

                <div className="flex flex-col gap-1">
                  <Button size="sm" variant="ghost" className="h-6 w-6 p-0">
                    {camera.isActive ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
                  </Button>
                  <Button size="sm" variant="ghost" className="h-6 w-6 p-0">
                    {camera.status === 'recording' ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {selectedCamera && (
        <div className="border-t p-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-lg flex items-center gap-2">
                <Camera className="w-4 h-4" />
                {selectedCamera.name}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {/* Mock Live Feed */}
              <div className="aspect-video bg-gray-900 rounded-lg relative overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-br from-gray-800 to-gray-900" />
                <div className="absolute top-2 left-2 bg-red-600 text-white text-xs px-2 py-1 rounded flex items-center gap-1">
                  <div className="w-2 h-2 bg-white rounded-full animate-pulse" />
                  LIVE
                </div>
                <div className="absolute bottom-2 left-2 text-white text-xs">
                  {selectedCamera.location}
                </div>
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="text-white/60 text-xs">Camera Feed</div>
                </div>
              </div>

              <div className="flex gap-2">
                <Button size="sm" className="flex-1">
                  <Search className="w-3 h-3 mr-1" />
                  AI Search
                </Button>
                <Button size="sm" variant="outline" className="flex-1">
                  <Clock className="w-3 h-3 mr-1" />
                  Playback
                </Button>
              </div>

              {selectedCamera.lastDetection && (
                <div className="p-2 bg-yellow-50 rounded border">
                  <div className="text-xs text-yellow-700">
                    <AlertTriangle className="w-3 h-3 inline mr-1" />
                    Recent Detection: {selectedCamera.detectionType} at {selectedCamera.lastDetection}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}