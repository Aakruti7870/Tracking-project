import { NativeModule, requireOptionalNativeModule } from "expo";

export declare class TripLocationNativeModule extends NativeModule {
  isAvailable(): boolean;
  startTracking(tripId: string, backendUrl: string, token: string): Promise<boolean>;
  stopTracking(): Promise<boolean>;
}

export default requireOptionalNativeModule<TripLocationNativeModule>("TripLocation");
