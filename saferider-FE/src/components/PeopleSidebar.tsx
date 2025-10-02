import { Clock, MapPin, Phone, Mail, Navigation, AlertTriangle, User } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Avatar, AvatarFallback } from "./ui/avatar";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";

interface Person {
  id: string;
  name: string;
  status: "missing" | "found" | "searching";
  lat: number;
  lng: number;
  phone?: string;
  email?: string;
  lastSeen?: string;
  age?: number;
  description?: string;
  reportedBy?: string;
  caseNumber?: string;
}

interface PeopleSidebarProps {
  people: Person[];
  selectedPerson: Person | null;
  onPersonSelect: (person: Person) => void;
}

export function PeopleSidebar({ people, selectedPerson, onPersonSelect }: PeopleSidebarProps) {
  const missingCount = people.filter(p => p.status === 'missing').length;
  const foundCount = people.filter(p => p.status === 'found').length;
  
  return (
    <div className="h-full flex flex-col">
      <div className="p-4 border-b">
        <div className="flex items-center gap-2 mb-2">
          <AlertTriangle className="w-5 h-5 text-red-600" />
          <h2 className="mb-0">Missing Persons</h2>
        </div>
        <div className="flex gap-4 text-sm text-muted-foreground">
          <span>{missingCount} missing</span>
          <span>{foundCount} found</span>
        </div>
      </div>
      
      <div className="flex-1 overflow-auto p-4 space-y-3">
        {people.map((person) => (
          <Card 
            key={person.id}
            className={`cursor-pointer transition-all duration-200 hover:shadow-md ${
              selectedPerson?.id === person.id ? 'ring-2 ring-blue-500 bg-blue-50' : ''
            }`}
            onClick={() => onPersonSelect(person)}
          >
            <CardContent className="p-4">
              <div className="flex items-start gap-3">
                <Avatar>
                  <AvatarFallback>{person.name.charAt(0)}</AvatarFallback>
                </Avatar>
                
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h4 className="truncate">{person.name}</h4>
                    <Badge 
                      variant="outline"
                      className={`text-xs ${
                        person.status === 'missing' 
                          ? 'border-red-500 text-red-700 bg-red-50' 
                          : person.status === 'found'
                          ? 'border-green-500 text-green-700 bg-green-50'
                          : 'border-yellow-500 text-yellow-700 bg-yellow-50'
                      }`}
                    >
                      {person.status}
                    </Badge>
                  </div>
                  
                  <div className="space-y-1 text-sm text-muted-foreground mb-2">
                    {person.age && <div>Age: {person.age}</div>}
                    {person.caseNumber && <div>Case: {person.caseNumber}</div>}
                  </div>
                  
                  <div className="space-y-1 text-xs text-muted-foreground">
                    <div className="flex items-center gap-1">
                      <MapPin className="w-3 h-3" />
                      <span>Lat: {person.lat.toFixed(3)}, Lng: {person.lng.toFixed(3)}</span>
                    </div>
                    
                    {person.lastSeen && (
                      <div className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        <span>Last seen: {person.lastSeen}</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
      
      {selectedPerson && (
        <div className="border-t p-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-lg flex items-center gap-2">
                <User className="w-4 h-4" />
                {selectedPerson.name}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {selectedPerson.description && (
                <div>
                  <label className="text-xs text-muted-foreground">Description</label>
                  <p className="text-sm">{selectedPerson.description}</p>
                </div>
              )}
              
              {selectedPerson.reportedBy && (
                <div className="flex items-center gap-2">
                  <User className="w-4 h-4 text-muted-foreground" />
                  <span className="text-sm">Reported by: {selectedPerson.reportedBy}</span>
                </div>
              )}
              
              {selectedPerson.phone && (
                <div className="flex items-center gap-2">
                  <Phone className="w-4 h-4 text-muted-foreground" />
                  <span className="text-sm">{selectedPerson.phone}</span>
                </div>
              )}
              
              <div className="flex gap-2">
                <Button size="sm" className="flex-1" variant={selectedPerson.status === 'missing' ? 'destructive' : 'default'}>
                  <Navigation className="w-3 h-3 mr-1" />
                  Search Area
                </Button>
                <Button size="sm" variant="outline" className="flex-1">
                  <AlertTriangle className="w-3 h-3 mr-1" />
                  Alert
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}