import petGirlIdle0 from "../assets/pet-girl-idle-0.png";
import petGirlIdle1 from "../assets/pet-girl-idle-1.png";
import petGirlIdle2 from "../assets/pet-girl-idle-2.png";
import petGirlIdle3 from "../assets/pet-girl-idle-3.png";
import petGirlIdle4 from "../assets/pet-girl-idle-4.png";
import petGirlIdle5 from "../assets/pet-girl-idle-5.png";
import petGirlIdle6 from "../assets/pet-girl-idle-6.png";
import petGirlIdle7 from "../assets/pet-girl-idle-7.png";
import petGirlThinking0 from "../assets/pet-girl-thinking-0.png";
import petGirlThinking1 from "../assets/pet-girl-thinking-1.png";
import petGirlThinking2 from "../assets/pet-girl-thinking-2.png";
import petGirlThinking3 from "../assets/pet-girl-thinking-3.png";

export const idlePetFrames = [
  petGirlIdle0,
  petGirlIdle1,
  petGirlIdle2,
  petGirlIdle3,
  petGirlIdle4,
  petGirlIdle5,
  petGirlIdle6,
  petGirlIdle7,
];

export const thinkingPetFrames = [
  petGirlThinking0,
  petGirlThinking1,
  petGirlThinking2,
  petGirlThinking3,
];

export const PET_FRAME_INTERVAL_MS = 220;

export function getPetAnimationFrames(isWorking) {
  return isWorking ? thinkingPetFrames : idlePetFrames;
}
