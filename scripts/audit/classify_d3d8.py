#!/usr/bin/env python3
"""Classify inventory candidates. Method-name classification is NOT receiver verification."""
import csv, json, collections, pathlib, argparse
D3D8=set("""QueryInterface AddRef Release GetAdapterCount GetAdapterIdentifier GetAdapterModeCount EnumAdapterModes GetAdapterDisplayMode CheckDeviceType CheckDeviceFormat CheckDeviceMultiSampleType CheckDepthStencilMatch GetDeviceCaps GetAdapterMonitor CreateDevice TestCooperativeLevel GetAvailableTextureMem GetDirect3D GetDisplayMode GetCreationParameters Reset Present GetBackBuffer SetGammaRamp GetGammaRamp CreateTexture CreateVolumeTexture CreateCubeTexture CreateVertexBuffer CreateIndexBuffer CreateRenderTarget CreateDepthStencilSurface CreateImageSurface CopyRects UpdateTexture GetFrontBuffer SetRenderTarget GetRenderTarget GetDepthStencilSurface BeginScene EndScene Clear SetTransform GetTransform MultiplyTransform SetViewport GetViewport SetMaterial GetMaterial SetLight GetLight LightEnable GetLightEnable SetClipPlane GetClipPlane SetRenderState GetRenderState BeginStateBlock EndStateBlock ApplyStateBlock CaptureStateBlock DeleteStateBlock CreateStateBlock SetClipStatus GetClipStatus SetTexture GetTexture GetTextureStageState SetTextureStageState ValidateDevice SetPaletteEntries GetPaletteEntries SetCurrentTexturePalette GetCurrentTexturePalette DrawPrimitive DrawIndexedPrimitive DrawPrimitiveUP DrawIndexedPrimitiveUP ProcessVertices CreateVertexShader SetVertexShader GetVertexShader DeleteVertexShader SetVertexShaderConstant GetVertexShaderConstant SetStreamSource GetStreamSource SetIndices GetIndices CreatePixelShader SetPixelShader GetPixelShader DeletePixelShader SetPixelShaderConstant GetPixelShaderConstant GetLevelDesc GetSurfaceLevel LockRect UnlockRect GetDesc Lock Unlock GetContainer GetDC ReleaseDC GetType GetLevelCount SetLOD GetLOD SetPriority GetPriority PreLoad GetPrivateData SetPrivateData FreePrivateData GetVolumeLevel LockBox UnlockBox GetCubeMapSurface GetDevice""".split())
def main():
 p=argparse.ArgumentParser()
 p.add_argument("input",help="calls.csv from inventory")
 p.add_argument("--output",default="build/d3d8-inventory/classified.csv")
 a=p.parse_args()
 rows=list(csv.DictReader(open(a.input,encoding="utf-8",newline="")))
 for r in rows:
  m=r["method"]
  r["category"]=("D3DX helper" if m.startswith("D3DX") else
   "DX8 wrapper macro" if r["kind"]=="dx8-macro" else
   "D3D8 method-name candidate" if m in D3D8 else
   "other C++ method")
  r["verified_receiver"]="NO"
 out=pathlib.Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
 with out.open("w",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else []);w.writeheader();w.writerows(rows)
 counts=collections.Counter(r["category"] for r in rows)
 print(json.dumps({"total":len(rows),"categories":counts},indent=2))
if __name__=="__main__":main()
