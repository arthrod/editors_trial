//! Round-trip a .docx through the WordCraft DOCX reader/writer.
//!
//! usage: wc-harness <input.docx> <output.docx>

use std::process::ExitCode;

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().collect();
    if args.len() != 3 {
        eprintln!("usage: wc-harness <input.docx> <output.docx>");
        return ExitCode::from(2);
    }
    let input = &args[1];
    let output = &args[2];

    let bytes = match std::fs::read(input) {
        Ok(b) => b,
        Err(e) => {
            eprintln!("FATAL: cannot read input {input}: {e}");
            return ExitCode::from(2);
        }
    };
    println!("input bytes : {}", bytes.len());

    let doc = match wordcraft_docx::read(&bytes) {
        Ok(d) => {
            println!("read        : ok via wordcraft_docx::read");
            d
        }
        Err(e) => {
            eprintln!("read        : FAILED via wordcraft_docx::read");
            eprintln!("read error display : {e}");
            eprintln!("read error debug   : {e:?}");
            eprintln!("retrying tolerant path: wordcraft_docx::read_with_password(bytes, None)");
            match wordcraft_docx::read_with_password(&bytes, None) {
                Ok(d) => {
                    println!("read        : ok via wordcraft_docx::read_with_password(bytes, None)");
                    d
                }
                Err(e2) => {
                    eprintln!("read_with_password error display : {e2}");
                    eprintln!("read_with_password error debug   : {e2:?}");
                    return ExitCode::from(1);
                }
            }
        }
    };

    let out_bytes = match wordcraft_docx::write(&doc) {
        Ok(b) => b,
        Err(e) => {
            eprintln!("write       : FAILED via wordcraft_docx::write");
            eprintln!("write error display : {e}");
            eprintln!("write error debug   : {e:?}");
            return ExitCode::from(1);
        }
    };

    if let Some(dir) = std::path::Path::new(output).parent() {
        let _ = std::fs::create_dir_all(dir);
    }
    if let Err(e) = std::fs::write(output, &out_bytes) {
        eprintln!("FATAL: cannot write output {output}: {e}");
        return ExitCode::from(2);
    }

    println!("output bytes: {}", out_bytes.len());
    let abs = std::fs::canonicalize(output)
        .map(|p| p.display().to_string())
        .unwrap_or_else(|_| output.clone());
    println!("output path : {abs}");
    ExitCode::SUCCESS
}
