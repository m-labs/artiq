// Uses `nalgebra` crate to invoke `np_linalg` and `sp_linalg` functions
// When converting between `nalgebra::Matrix` and `NDArray` following considerations are necessary
//
// * Both `nalgebra::Matrix` and `NDArray` require their content to be stored in row-major order
// * `NDArray` data pointer can be directly read and converted to `nalgebra::Matrix` (row and column number must be known)
// * `nalgebra::Matrix::as_slice` returns the content of matrix in column-major order and initial data needs to be transposed before storing it in `NDArray` data pointer

use alloc::vec::Vec;
use core::slice;

use nalgebra::DMatrix;

use crate::artiq_raise;

pub struct InputMatrix {
    pub ndims: usize,
    pub dims: *const usize,
    pub data: *mut f64,
}

impl InputMatrix {
    fn get_dims(&mut self) -> Vec<usize> {
        let dims = unsafe { slice::from_raw_parts(self.dims, self.ndims) };
        dims.to_vec()
    }
}

/// # Safety
///
/// `mat1` should point to a valid 2DArray of `f64` floats in row-major order
#[no_mangle]
pub unsafe extern "C" fn np_linalg_cholesky(mat1: *mut InputMatrix, out: *mut InputMatrix) {
    let mat1 = mat1.as_mut().unwrap();
    let out = out.as_mut().unwrap();

    if mat1.ndims != 2 {
        artiq_raise!(
            "ValueError",
            "expected 2D Vector Input, but received {1}D input)",
            0,
            mat1.ndims as i64,
            0
        );
    }

    let dim1 = (*mat1).get_dims();
    if dim1[0] != dim1[1] {
        artiq_raise!(
            "ValueError",
            "last 2 dimensions of the array must be square: {1} != {2}",
            0,
            dim1[0] as i64,
            dim1[1] as i64
        );
    }

    let outdim = out.get_dims();
    let out_slice = unsafe { slice::from_raw_parts_mut(out.data, outdim[0] * outdim[1]) };
    let data_slice1 = unsafe { slice::from_raw_parts_mut(mat1.data, dim1[0] * dim1[1]) };

    let matrix1 = DMatrix::from_row_slice(dim1[0], dim1[1], data_slice1);
    let result = matrix1.cholesky();
    match result {
        Some(res) => {
            out_slice.copy_from_slice(res.unpack().transpose().as_slice());
        }
        None => {
            artiq_raise!("LinAlgError", "Matrix is not positive definite");
        }
    };
}

/// # Safety
///
/// `mat1` should point to a valid 2DArray of `f64` floats in row-major order
#[no_mangle]
pub unsafe extern "C" fn np_linalg_qr(mat1: *mut InputMatrix, out_q: *mut InputMatrix, out_r: *mut InputMatrix) {
    let mat1 = mat1.as_mut().unwrap();
    let out_q = out_q.as_mut().unwrap();
    let out_r = out_r.as_mut().unwrap();

    if mat1.ndims != 2 {
        artiq_raise!(
            "ValueError",
            "expected 2D Vector Input, but received {1}D input)",
            0,
            mat1.ndims as i64,
            0
        );
    }

    let dim1 = (*mat1).get_dims();
    let outq_dim = (*out_q).get_dims();
    let outr_dim = (*out_r).get_dims();

    let data_slice1 = unsafe { slice::from_raw_parts_mut(mat1.data, dim1[0] * dim1[1]) };
    let out_q_slice = unsafe { slice::from_raw_parts_mut(out_q.data, outq_dim[0] * outq_dim[1]) };
    let out_r_slice = unsafe { slice::from_raw_parts_mut(out_r.data, outr_dim[0] * outr_dim[1]) };

    // Refer to https://github.com/dimforge/nalgebra/issues/735
    let matrix1 = DMatrix::from_row_slice(dim1[0], dim1[1], data_slice1);

    let res = matrix1.qr();
    let (q, r) = res.unpack();

    // Uses different algo need to match numpy
    out_q_slice.copy_from_slice(q.transpose().as_slice());
    out_r_slice.copy_from_slice(r.transpose().as_slice());
}

/// # Safety
///
/// `mat1` should point to a valid 2DArray of `f64` floats in row-major order
#[no_mangle]
pub unsafe extern "C" fn np_linalg_svd(
    mat1: *mut InputMatrix,
    outu: *mut InputMatrix,
    outs: *mut InputMatrix,
    outvh: *mut InputMatrix,
) {
    let mat1 = mat1.as_mut().unwrap();
    let outu = outu.as_mut().unwrap();
    let outs = outs.as_mut().unwrap();
    let outvh = outvh.as_mut().unwrap();

    if mat1.ndims != 2 {
        artiq_raise!(
            "ValueError",
            "expected 2D Vector Input, but received {1}D input)",
            0,
            mat1.ndims as i64,
            0
        );
    }

    let dim1 = (*mat1).get_dims();
    let outu_dim = (*outu).get_dims();
    let outs_dim = (*outs).get_dims();
    let outvh_dim = (*outvh).get_dims();

    let data_slice1 = unsafe { slice::from_raw_parts_mut(mat1.data, dim1[0] * dim1[1]) };
    let out_u_slice = unsafe { slice::from_raw_parts_mut(outu.data, outu_dim[0] * outu_dim[1]) };
    let out_s_slice = unsafe { slice::from_raw_parts_mut(outs.data, outs_dim[0]) };
    let out_vh_slice = unsafe { slice::from_raw_parts_mut(outvh.data, outvh_dim[0] * outvh_dim[1]) };

    let matrix = DMatrix::from_row_slice(dim1[0], dim1[1], data_slice1);
    let result = matrix.svd(true, true);
    out_u_slice.copy_from_slice(result.u.unwrap().transpose().as_slice());
    out_s_slice.copy_from_slice(result.singular_values.as_slice());
    out_vh_slice.copy_from_slice(result.v_t.unwrap().transpose().as_slice());
}

/// # Safety
///
/// `mat1` should point to a valid 2DArray of `f64` floats in row-major order
#[no_mangle]
pub unsafe extern "C" fn np_linalg_inv(mat1: *mut InputMatrix, out: *mut InputMatrix) {
    let mat1 = mat1.as_mut().unwrap();
    let out = out.as_mut().unwrap();

    if mat1.ndims != 2 {
        artiq_raise!(
            "ValueError",
            "expected 2D Vector Input, but received {1}D input)",
            0,
            mat1.ndims as i64,
            0
        );
    }
    let dim1 = (*mat1).get_dims();

    if dim1[0] != dim1[1] {
        artiq_raise!(
            "ValueError",
            "last 2 dimensions of the array must be square: {1} != {2}",
            0,
            dim1[0] as i64,
            dim1[1] as i64
        );
    }

    let outdim = out.get_dims();
    let out_slice = unsafe { slice::from_raw_parts_mut(out.data, outdim[0] * outdim[1]) };
    let data_slice1 = unsafe { slice::from_raw_parts_mut(mat1.data, dim1[0] * dim1[1]) };

    let matrix = DMatrix::from_row_slice(dim1[0], dim1[1], data_slice1);
    if !matrix.is_invertible() {
        artiq_raise!("LinAlgError", "no inverse for Singular Matrix");
    }
    let inv = matrix.try_inverse().unwrap();
    out_slice.copy_from_slice(inv.transpose().as_slice());
}

/// # Safety
///
/// `mat1` should point to a valid 2DArray of `f64` floats in row-major order
#[no_mangle]
pub unsafe extern "C" fn np_linalg_pinv(mat1: *mut InputMatrix, out: *mut InputMatrix) {
    let mat1 = mat1.as_mut().unwrap();
    let out = out.as_mut().unwrap();

    if mat1.ndims != 2 {
        artiq_raise!(
            "ValueError",
            "expected 2D Vector Input, but received {1}D input)",
            0,
            mat1.ndims as i64,
            0
        );
    }
    let dim1 = (*mat1).get_dims();
    let outdim = out.get_dims();
    let out_slice = unsafe { slice::from_raw_parts_mut(out.data, outdim[0] * outdim[1]) };
    let data_slice1 = unsafe { slice::from_raw_parts_mut(mat1.data, dim1[0] * dim1[1]) };

    let matrix = DMatrix::from_row_slice(dim1[0], dim1[1], data_slice1);
    let svd = matrix.svd(true, true);
    let inv = svd.pseudo_inverse(1e-15);

    match inv {
        Ok(m) => {
            out_slice.copy_from_slice(m.transpose().as_slice());
        }
        Err(_) => {
            artiq_raise!("LinAlgError", "SVD computation does not converge");
        }
    }
}

/// # Safety
///
/// `mat1` should point to a valid 2DArray of `f64` floats in row-major order
#[no_mangle]
pub unsafe extern "C" fn np_linalg_matrix_power(mat1: *mut InputMatrix, mat2: *mut InputMatrix, out: *mut InputMatrix) {
    let mat1 = mat1.as_mut().unwrap();
    let mat2 = mat2.as_mut().unwrap();
    let out = out.as_mut().unwrap();

    if mat1.ndims != 2 {
        artiq_raise!(
            "ValueError",
            "expected 2D Vector Input, but received {1}D input)",
            0,
            mat1.ndims as i64,
            0
        );
    }

    let dim1 = (*mat1).get_dims();
    let power = unsafe { slice::from_raw_parts_mut(mat2.data, 1) };
    let power = power[0];
    let outdim = out.get_dims();
    let out_slice = unsafe { slice::from_raw_parts_mut(out.data, outdim[0] * outdim[1]) };
    let data_slice1 = unsafe { slice::from_raw_parts_mut(mat1.data, dim1[0] * dim1[1]) };
    let mut abs_power = power;
    if abs_power < 0.0 {
        abs_power = abs_power * -1.0;
    }
    let matrix1 = DMatrix::from_row_slice(dim1[0], dim1[1], data_slice1);
    if !matrix1.is_square() {
        artiq_raise!(
            "ValueError",
            "last 2 dimensions of the array must be square: {1} != {2}",
            0,
            dim1[0] as i64,
            dim1[1] as i64
        );
    }
    let mut result = matrix1.pow(abs_power as u32);

    if power < 0.0 {
        if !matrix1.is_invertible() {
            artiq_raise!("LinAlgError", "no inverse for Singular Matrix");
        }
        result = result.try_inverse().unwrap();
    }
    out_slice.copy_from_slice(result.transpose().as_slice());
}

/// # Safety
///
/// `mat1` should point to a valid 2DArray of `f64` floats in row-major order
#[no_mangle]
pub unsafe extern "C" fn np_linalg_det(mat1: *mut InputMatrix, out: *mut InputMatrix) {
    let mat1 = mat1.as_mut().unwrap();
    let out = out.as_mut().unwrap();

    if mat1.ndims != 2 {
        artiq_raise!(
            "ValueError",
            "expected 2D Vector Input, but received {1}D input)",
            0,
            mat1.ndims as i64,
            0
        );
    }
    let dim1 = (*mat1).get_dims();
    let out_slice = unsafe { slice::from_raw_parts_mut(out.data, 1) };
    let data_slice1 = unsafe { slice::from_raw_parts_mut(mat1.data, dim1[0] * dim1[1]) };

    let matrix = DMatrix::from_row_slice(dim1[0], dim1[1], data_slice1);
    if !matrix.is_square() {
        artiq_raise!(
            "ValueError",
            "last 2 dimensions of the array must be square: {1} != {2}",
            0,
            dim1[0] as i64,
            dim1[1] as i64
        );
    }
    out_slice[0] = matrix.determinant();
}

/// # Safety
///
/// `mat1` should point to a valid 2DArray of `f64` floats in row-major order
#[no_mangle]
pub unsafe extern "C" fn sp_linalg_lu(mat1: *mut InputMatrix, out_l: *mut InputMatrix, out_u: *mut InputMatrix) {
    let mat1 = mat1.as_mut().unwrap();
    let out_l = out_l.as_mut().unwrap();
    let out_u = out_u.as_mut().unwrap();

    if mat1.ndims != 2 {
        artiq_raise!(
            "ValueError",
            "expected 2D Vector Input, but received {1}D input)",
            0,
            mat1.ndims as i64,
            0
        );
    }

    let dim1 = (*mat1).get_dims();
    let outl_dim = (*out_l).get_dims();
    let outu_dim = (*out_u).get_dims();

    let data_slice1 = unsafe { slice::from_raw_parts_mut(mat1.data, dim1[0] * dim1[1]) };
    let out_l_slice = unsafe { slice::from_raw_parts_mut(out_l.data, outl_dim[0] * outl_dim[1]) };
    let out_u_slice = unsafe { slice::from_raw_parts_mut(out_u.data, outu_dim[0] * outu_dim[1]) };

    let matrix = DMatrix::from_row_slice(dim1[0], dim1[1], data_slice1);
    let (_, l, u) = matrix.lu().unpack();

    out_l_slice.copy_from_slice(l.transpose().as_slice());
    out_u_slice.copy_from_slice(u.transpose().as_slice());
}

/// # Safety
///
/// `mat1` should point to a valid 2DArray of `f64` floats in row-major order
#[no_mangle]
pub unsafe extern "C" fn sp_linalg_schur(mat1: *mut InputMatrix, out_t: *mut InputMatrix, out_z: *mut InputMatrix) {
    let mat1 = mat1.as_mut().unwrap();
    let out_t = out_t.as_mut().unwrap();
    let out_z = out_z.as_mut().unwrap();

    if mat1.ndims != 2 {
        artiq_raise!(
            "ValueError",
            "expected 2D Vector Input, but received {1}D input)",
            0,
            mat1.ndims as i64,
            0
        );
    }

    let dim1 = (*mat1).get_dims();

    if dim1[0] != dim1[1] {
        artiq_raise!(
            "ValueError",
            "last 2 dimensions of the array must be square: {1} != {2}",
            0,
            dim1[0] as i64,
            dim1[1] as i64
        );
    }

    let out_t_dim = (*out_t).get_dims();
    let out_z_dim = (*out_z).get_dims();

    let data_slice1 = unsafe { slice::from_raw_parts_mut(mat1.data, dim1[0] * dim1[1]) };
    let out_t_slice = unsafe { slice::from_raw_parts_mut(out_t.data, out_t_dim[0] * out_t_dim[1]) };
    let out_z_slice = unsafe { slice::from_raw_parts_mut(out_z.data, out_z_dim[0] * out_z_dim[1]) };

    let matrix = DMatrix::from_row_slice(dim1[0], dim1[1], data_slice1);
    let (z, t) = matrix.schur().unpack();

    out_t_slice.copy_from_slice(t.transpose().as_slice());
    out_z_slice.copy_from_slice(z.transpose().as_slice());
}

/// # Safety
///
/// `mat1` should point to a valid 2DArray of `f64` floats in row-major order
#[no_mangle]
pub unsafe extern "C" fn sp_linalg_hessenberg(
    mat1: *mut InputMatrix,
    out_h: *mut InputMatrix,
    out_q: *mut InputMatrix,
) {
    let mat1 = mat1.as_mut().unwrap();
    let out_h = out_h.as_mut().unwrap();
    let out_q = out_q.as_mut().unwrap();

    if mat1.ndims != 2 {
        artiq_raise!(
            "ValueError",
            "expected 2D Vector Input, but received {1}D input)",
            0,
            mat1.ndims as i64,
            0
        );
    }

    let dim1 = (*mat1).get_dims();

    if dim1[0] != dim1[1] {
        artiq_raise!(
            "ValueError",
            "last 2 dimensions of the array must be square: {1} != {2}",
            0,
            dim1[0] as i64,
            dim1[1] as i64
        );
    }

    let out_h_dim = (*out_h).get_dims();
    let out_q_dim = (*out_q).get_dims();

    let data_slice1 = unsafe { slice::from_raw_parts_mut(mat1.data, dim1[0] * dim1[1]) };
    let out_h_slice = unsafe { slice::from_raw_parts_mut(out_h.data, out_h_dim[0] * out_h_dim[1]) };
    let out_q_slice = unsafe { slice::from_raw_parts_mut(out_q.data, out_q_dim[0] * out_q_dim[1]) };

    let matrix = DMatrix::from_row_slice(dim1[0], dim1[1], data_slice1);
    let (q, h) = matrix.hessenberg().unpack();

    out_h_slice.copy_from_slice(h.transpose().as_slice());
    out_q_slice.copy_from_slice(q.transpose().as_slice());
}
