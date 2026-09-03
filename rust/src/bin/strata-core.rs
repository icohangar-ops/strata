use std::io::{self, Read};

use strata_core::{handle_request, StrataRequest};

fn main() {
    if let Err(error) = run() {
        eprintln!("{}", error);
        std::process::exit(1);
    }
}

fn run() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: StrataRequest = serde_json::from_str(&input)?;
    let response = handle_request(request);
    println!("{}", serde_json::to_string(&response)?);
    Ok(())
}
