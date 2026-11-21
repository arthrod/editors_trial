//! Round-trip a .docx through OpenDoc's own engine, with no browser.
//!
//! usage: opendoc-harness <input.docx> <output.docx> [preserve|semantic|exact]
//!
//! This is what OpenDoc's own command line does for
//! `opendoc convert IN.docx OUT.docx` (repos/opendoc/tools/opendoc-cli/src/main.rs,
//! `fn convert`): `opendoc::Document::open` (crates/opendoc/src/document.rs),
//! then `Document::save(Format::Docx, mode)`.
//!
//! The mode is the command line's own default for a same-format save,
//! `SaveMode::PreserveWhenSafe`: the package is written again from the model,
//! and source parts the model does not represent are carried over verbatim.
//! It is also what the editor application writes for a document that was
//! edited (webapp/src/editor_save.mjs asks for `exact_if_unchanged` first and
//! falls back to `preserve_when_safe`).
//!
//! `exact` returns the source bytes for an unchanged document, which measures
//! nothing; `semantic` writes from the model alone. Both are here only so the
//! difference can be shown; the trial's lane is `preserve`.

use std::process::ExitCode;
use std::time::Instant;

use opendoc::{Document, Format, SaveMode};

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().collect();
    if args.len() != 3 && args.len() != 4 {
        eprintln!("usage: opendoc-harness <input.docx> <output.docx> [preserve|semantic|exact]");
        return ExitCode::from(2);
    }
    let (input, output) = (&args[1], &args[2]);
    let mode = match args.get(3).map_or("preserve", String::as_str) {
        "preserve" => SaveMode::PreserveWhenSafe,
        "semantic" => SaveMode::Semantic,
        "exact" => SaveMode::Exact,
        other => {
            eprintln!("unknown mode {other}: preserve, semantic or exact");
            return ExitCode::from(2);
        }
    };

    let bytes = match std::fs::read(input) {
        Ok(b) => b,
        Err(e) => {
            eprintln!("FATAL: cannot read input {input}: {e}");
            return ExitCode::from(2);
        }
    };
    println!("input bytes : {}", bytes.len());

    let t0 = Instant::now();
    let doc = match Document::open(&bytes) {
        Ok(d) => d,
        Err(e) => {
            eprintln!("open        : FAILED via opendoc::Document::open");
            eprintln!("open error display : {e}");
            eprintln!("open error debug   : {e:?}");
            return ExitCode::from(1);
        }
    };
    println!("PERF model_ready_ms={:.6}", t0.elapsed().as_secs_f64() * 1000.0);
    println!(
        "open        : ok via opendoc::Document::open (source format {})",
        doc.source_format().map_or("?", Format::name)
    );

    let t_save = Instant::now();
    let (out_bytes, report) = match doc.save(Format::Docx, mode) {
        Ok(saved) => saved,
        Err(e) => {
            eprintln!("save        : FAILED via opendoc::Document::save");
            eprintln!("save error display : {e}");
            eprintln!("save error debug   : {e:?}");
            return ExitCode::from(1);
        }
    };
    println!("PERF save_ms={:.6}", t_save.elapsed().as_secs_f64() * 1000.0);
    println!(
        "save        : ok via opendoc::Document::save(Docx, {}), {} finding(s), {} loss(es) in its own report",
        report.mode,
        report.findings.len(),
        report.losses.len()
    );
    for loss in &report.losses {
        println!("  loss      : {loss:?}");
    }

    if let Some(parent) = std::path::Path::new(output).parent().filter(|p| !p.as_os_str().is_empty()) {
        if let Err(e) = std::fs::create_dir_all(parent) {
            eprintln!("FATAL: cannot create {}: {e}", parent.display());
            return ExitCode::from(2);
        }
    }
    if let Err(e) = std::fs::write(output, &out_bytes) {
        eprintln!("FATAL: cannot write output {output}: {e}");
        return ExitCode::from(2);
    }
    println!(
        "output bytes: {}{}",
        out_bytes.len(),
        if out_bytes == bytes { "  IDENTICAL TO INPUT (pass-through)" } else { "" }
    );
    ExitCode::SUCCESS
}
