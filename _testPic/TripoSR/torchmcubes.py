import mcubes
import torch
import numpy as np

def marching_cubes(grid, thresh):
    """
    這是一個相容性 Wrapper，用於替代原本的 torchmcubes.marching_cubes。
    它內部使用 PyMCubes (CPU) 來執行運算，避免 Windows 下的 DLL 載入錯誤。
    """
    # 如果 grid 是 Tensor，先轉回 CPU numpy array
    if isinstance(grid, torch.Tensor):
        grid = grid.detach().cpu().numpy()
    
    # 呼叫 PyMCubes 進行運算
    # PyMCubes 回傳的是 (verts, faces)
    verts, faces = mcubes.marching_cubes(grid, thresh)
    
    # 將結果轉回 PyTorch Tensor，並轉為正確的型別
    # TripoSR 預期 verts 是 FloatTensor, faces 是 LongTensor
    verts_tensor = torch.from_numpy(verts).to(dtype=torch.float32)
    faces_tensor = torch.from_numpy(faces.astype(np.int64))
    
    return verts_tensor, faces_tensor
